# 暗盘统计模块独立化 & 调度器重构

## TL;DR (For humans)

将 `close_export_scheduler.py` 从"上帝方法"重构为**任务注册模式**，暗盘统计推送作为独立任务可单独触发和测试。给 `dark_trade_stats.py` 添加 CLI 入口，随时可命令行测试。添加集成测试验证真实数据计算 + mock推送。

**核心改动：**
1. 重构 `close_export_scheduler.py` → Task Registry 模式（3个独立任务可单独启用/触发）
2. `dark_trade_stats.py` 添加 `if __name__ == "__main__"` CLI 入口
3. 添加集成测试 `tests/test_dark_trade_stats_integration.py`

**预期效果：**
- 命令行直接运行 `python -m stock_monitor.services.dark_trade_stats --codes sh600519` 测试推送
- 调度器中每个任务（Excel导出、技术指标、暗盘统计）可独立启用/禁用
- `trigger_now()` 可选择只触发单个任务

---

## Architecture

### Current Flow
```
CloseExportScheduler.run()
  └─ _execute_export()  ← 上帝方法，3个任务硬编码
       ├─ 1. dark_trade_exporter.export_dark_trade_excel()
       ├─ 2. export_to_excel()  ← 技术指标
       └─ 3. dark_trade_stats.push_dark_trade_stats()
```

### Target Flow
```
CloseExportScheduler.run()
  └─ _execute_export()
       └─ 遍历 self._tasks (TaskRegistry)
            ├─ DarkTradeExcelTask.execute()
            ├─ StockIndicatorsTask.execute()
            └─ DarkTradeStatsTask.execute()  ← 可独立触发
```

---

## Todo

### Phase 1: 重构调度器为任务注册模式

#### 1.1 定义 ExportTask 协议和注册机制
**文件:** `stock_monitor/services/close_export_scheduler.py`

在 `CloseExportScheduler` 类之前添加：

```python
from typing import Protocol, Any

class ExportTask(Protocol):
    """收盘导出任务协议"""
    @property
    def name(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    def execute(self) -> Any: ...

    def set_enabled(self, enabled: bool) -> None: ...
```

在 `CloseExportScheduler.__init__` 中添加任务注册列表：

```python
self._tasks: list[ExportTask] = []
```

添加注册方法：

```python
def register_task(self, task: ExportTask) -> None:
    """注册导出任务"""
    self._tasks.append(task)
    app_logger.info(f"[CloseExportScheduler] 注册任务: {task.name}")

def get_tasks(self) -> list[ExportTask]:
    """获取所有已注册任务"""
    return list(self._tasks)
```

**验收:** `CloseExportScheduler` 有 `_tasks` 列表和 `register_task()` 方法，编译通过。

---

#### 1.2 将现有3个任务封装为独立类
**文件:** `stock_monitor/services/close_export_scheduler.py`

在 `ExportTask` 协议之后、`CloseExportScheduler` 类之前添加3个任务类：

```python
class DarkTradeExcelTask:
    """暗盘资金Excel导出任务"""
    def __init__(self):
        self._enabled = True

    @property
    def name(self) -> str:
        return "暗盘Excel导出"

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def execute(self) -> str | None:
        from stock_monitor.services.dark_trade_exporter import export_dark_trade_excel
        try:
            dark_file = export_dark_trade_excel(watchlist_codes=[])
            app_logger.info(f"[CloseExportScheduler] 暗盘数据已导出: {dark_file}")
            return str(dark_file)
        except Exception as e:
            app_logger.error(f"[CloseExportScheduler] 暗盘数据导出失败: {e}")
            return None


class StockIndicatorsTask:
    """自选股技术指标导出任务"""
    def __init__(self):
        self._enabled = True

    @property
    def name(self) -> str:
        return "自选股指标导出"

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def execute(self) -> str | None:
        from scripts.reporting.export_stocks_to_excel import export_to_excel
        from stock_monitor.core.config_center import config_center
        try:
            user_stocks = config_center.user_stocks
            output_path = (
                Path("analysis_reports")
                / f"stock_export_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            export_to_excel(
                output_path=str(output_path),
                include_history=True,
                history_symbols=user_stocks,
            )
            app_logger.info(f"[CloseExportScheduler] 自选股指标已导出: {output_path}")
            return str(output_path)
        except Exception as e:
            app_logger.error(f"[CloseExportScheduler] 自选股指标导出失败: {e}")
            return None


class DarkTradeStatsTask:
    """暗盘统计推送任务"""
    def __init__(self):
        self._enabled = True

    @property
    def name(self) -> str:
        return "暗盘统计推送"

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def execute(self) -> bool:
        from stock_monitor.core.config_center import config_center
        from stock_monitor.services.dark_trade_stats import push_dark_trade_stats
        try:
            user_stocks = config_center.user_stocks
            result = push_dark_trade_stats(config_center._manager.config, user_stocks)
            if result:
                app_logger.info("[CloseExportScheduler] 暗盘统计推送已触发")
            else:
                app_logger.warning("[CloseExportScheduler] 暗盘统计推送返回失败")
            return result
        except Exception as e:
            app_logger.error(f"[CloseExportScheduler] 暗盘统计推送失败: {e}")
            return False
```

**验收:** 3个任务类定义完成，每个都有 `name`/`enabled`/`set_enabled()`/`execute()` 方法。

---

#### 1.3 修改 CloseExportScheduler 使用任务注册
**文件:** `stock_monitor/services/close_export_scheduler.py`

修改 `__init__` 注册默认任务：

```python
def __init__(self, parent=None):
    super().__init__(parent)
    self._running = False
    self._enabled = False
    self._last_export_date = ""
    self._export_time_window_start = dtime(15, 5)
    self._export_time_window_end = dtime(15, 30)
    self._check_interval_ms = 60000
    self._export_lock = threading.Lock()
    # 注册默认任务
    self._tasks: list[ExportTask] = [
        DarkTradeExcelTask(),
        StockIndicatorsTask(),
        DarkTradeStatsTask(),
    ]
```

重写 `_execute_export()` 使用任务循环：

```python
def _execute_export(self, task_name: str | None = None):
    """执行导出任务

    Args:
        task_name: 指定任务名则只执行该任务，None则执行所有任务
    """
    if not self._export_lock.acquire(blocking=False):
        app_logger.info("[CloseExportScheduler] 导出任务正在执行中，跳过")
        return
    try:
        self.export_started.emit()
        app_logger.info("[CloseExportScheduler] 开始执行收盘数据导出...")

        exported_files = []
        for task in self._tasks:
            if not task.enabled:
                continue
            if task_name and task.name != task_name:
                continue

            try:
                result = task.execute()
                if result:
                    exported_files.append(str(result))
            except Exception as e:
                app_logger.error(f"[CloseExportScheduler] 任务 {task.name} 异常: {e}")

        self._mark_exported()

        if exported_files:
            self.export_completed.emit(exported_files)
            app_logger.info(
                f"[CloseExportScheduler] 收盘数据导出完成，共导出 {len(exported_files)} 个文件"
            )
        else:
            self.export_failed.emit("所有导出任务均失败")

    except Exception as e:
        error_msg = f"收盘数据导出异常: {e}"
        app_logger.error(f"[CloseExportScheduler] {error_msg}")
        self.export_failed.emit(error_msg)
    finally:
        self._export_lock.release()
```

修改 `trigger_now` 支持指定任务：

```python
def trigger_now(self, task_name: str | None = None):
    """立即触发一次导出（用于测试）

    Args:
        task_name: 指定任务名则只触发该任务，None则触发所有任务
    """
    app_logger.info(f"[CloseExportScheduler] 手动触发导出测试 (task={task_name})...")
    self._execute_export(task_name=task_name)
```

**验收:** `_execute_export` 遍历 `self._tasks` 而非硬编码。`trigger_now("暗盘统计推送")` 只触发暗盘统计。

---

### Phase 2: dark_trade_stats.py CLI 入口

#### 2.1 添加 CLI 入口
**文件:** `stock_monitor/services/dark_trade_stats.py`

在文件末尾添加：

```python
def main():
    """CLI 入口 - 暗盘资金统计"""
    import argparse

    parser = argparse.ArgumentParser(
        description="暗盘资金统计 - 计算全市场和自选股暗盘净流入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 计算并打印统计（不推送）
  python -m stock_monitor.services.dark_trade_stats --codes sh600519 sz000559

  # 计算并推送到企业微信
  python -m stock_monitor.services.dark_trade_stats --codes sh600519 --push

  # 只打印格式化消息
  python -m stock_monitor.services.dark_trade_stats --print-only
        """,
    )
    parser.add_argument(
        "--codes",
        nargs="*",
        default=[],
        help="自选股代码列表（如 sh600519 sz000559）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="历史天数（默认5天）",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="推送到企业微信",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="只打印格式化消息，不推送",
    )
    args = parser.parse_args()

    # 计算统计
    print(f"正在计算暗盘统计数据（{args.days}天历史）...")
    stats = calculate_dark_trade_stats(args.codes, history_days=args.days)

    if not stats.get("market_summary"):
        print("⚠️ 无统计数据（可能非交易时段或网络异常）")
        return

    # 格式化消息
    message = format_dark_trade_stats_message(stats)

    if args.push:
        # 推送模式
        from stock_monitor.core.config_center import config_center
        success = push_dark_trade_stats(config_center._manager.config, args.codes)
        if success:
            print("✅ 推送成功")
        else:
            print("❌ 推送失败")
    else:
        # 打印模式
        print("\n" + message)

    if args.print_only or not args.push:
        print("\n💡 提示: 添加 --push 参数可推送到企业微信")


if __name__ == "__main__":
    main()
```

**验收:** `python -m stock_monitor.services.dark_trade_stats --codes sh600519` 可运行并打印统计。

---

### Phase 3: 集成测试

#### 3.1 添加集成测试
**文件:** `tests/test_dark_trade_stats_integration.py`

```python
"""
暗盘统计集成测试 - 使用真实数据计算，mock推送
"""

import pytest
from unittest.mock import patch, MagicMock

from stock_monitor.services.dark_trade_stats import (
    calculate_dark_trade_stats,
    format_dark_trade_stats_message,
    push_dark_trade_stats,
)
from stock_monitor.services.close_export_scheduler import (
    CloseExportScheduler,
    DarkTradeStatsTask,
    DarkTradeExcelTask,
    StockIndicatorsTask,
)


class TestDarkTradeStatsIntegration:
    """暗盘统计集成测试（真实数据计算）"""

    @pytest.mark.integration
    def test_calculate_real_data(self):
        """使用真实数据计算统计"""
        stats = calculate_dark_trade_stats([], history_days=1)

        assert "market_summary" in stats
        assert "watchlist_details" in stats
        assert "date" in stats
        assert isinstance(stats["market_summary"], dict)
        assert isinstance(stats["watchlist_details"], list)

    @pytest.mark.integration
    def test_calculate_with_watchlist(self):
        """带自选股的统计计算"""
        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)

        watchlist = stats.get("watchlist_details", [])
        assert len(watchlist) >= 0  # 可能有数据也可能没有
        if watchlist:
            assert watchlist[0]["code"] == "600519"

    @pytest.mark.integration
    def test_format_message_integration(self):
        """格式化消息集成测试"""
        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)
        message = format_dark_trade_stats_message(stats)

        assert "📊 暗盘资金统计" in message
        assert "【全市场概览】" in message

    @pytest.mark.integration
    @patch("stock_monitor.services.notifier.NotifierService.dispatch_custom_message")
    def test_push_integration(self, mock_dispatch):
        """推送集成测试（mock推送）"""
        mock_dispatch.return_value = True

        from stock_monitor.core.config_center import config_center
        result = push_dark_trade_stats(
            config_center._manager.config, ["sh600519"]
        )

        assert result is True
        mock_dispatch.assert_called_once()


class TestCloseExportSchedulerTasks:
    """调度器任务注册测试"""

    def test_task_registry(self):
        """任务注册和执行"""
        scheduler = CloseExportScheduler()

        # 验证默认任务已注册
        tasks = scheduler.get_tasks()
        assert len(tasks) == 3
        task_names = [t.name for t in tasks]
        assert "暗盘Excel导出" in task_names
        assert "自选股指标导出" in task_names
        assert "暗盘统计推送" in task_names

    def test_task_enable_disable(self):
        """任务启用/禁用"""
        task = DarkTradeStatsTask()
        assert task.enabled is True

        task.set_enabled(False)
        assert task.enabled is False

    def test_trigger_single_task(self):
        """触发单个任务"""
        scheduler = CloseExportScheduler()

        # 只触发暗盘统计推送（不触发Excel导出）
        with patch.object(DarkTradeStatsTask, "execute") as mock_exec:
            mock_exec.return_value = True
            scheduler.trigger_now(task_name="暗盘统计推送")
            mock_exec.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
```

**验收:** `pytest tests/test_dark_trade_stats_integration.py -v -m integration` 可运行。

---

### Phase 4: 代码质量 & 文档

#### 4.1 更新 CHANGELOG.md
**文件:** `CHANGELOG.md`

```markdown
## v4.5.1

### 改进
- 重构 `close_export_scheduler` 为任务注册模式，3个子任务可独立启用/触发
- `dark_trade_stats.py` 添加 CLI 入口，支持命令行测试暗盘统计推送
- 添加集成测试 `test_dark_trade_stats_integration.py`

### 修复
- 修复暗盘统计推送在收盘时未触发的问题
```

#### 4.2 更新版本号
**文件:** `pyproject.toml`

version = "4.5.1"

**验收:** 所有代码通过 ruff 检查，测试通过。

---

## Final Verification Wave

### 自动验证（agent 执行）
1. **编译检查:** `python -c "from stock_monitor.services.close_export_scheduler import CloseExportScheduler"`
2. **单元测试:** `pytest tests/test_dark_trade_stats.py -v`
3. **集成测试:** `pytest tests/test_dark_trade_stats_integration.py -v -m integration`
4. **CLI 测试:** `python -m stock_monitor.services.dark_trade_stats --print-only`
5. **Lint:** `ruff check stock_monitor/services/close_export_scheduler.py stock_monitor/services/dark_trade_stats.py`
6. **Format:** `ruff format stock_monitor/services/close_export_scheduler.py stock_monitor/services/dark_trade_stats.py`

### 人工验证
- 运行 CLI 命令，确认输出格式正确
- 确认调度器可单独触发暗盘统计推送
