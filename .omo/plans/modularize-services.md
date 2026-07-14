# 服务层模块化重构计划

## 目标

将 `services/` 下的暗盘相关模块重构为清晰的包结构，消除重复代码，解耦职责，提升可维护性。

---

## 现状分析

### 当前文件结构

```
services/
├── __init__.py              # 空
├── dark_trade_stats.py      # 417行 - 计算+格式化+推送+导出+CLI (职责过多)
├── dark_trade_exporter.py   # 467行 - 全市场数据抓取+Excel/CSV导出
├── dark_trade_service.py    # 370行 - 后台服务+缓存+线程
├── close_export_scheduler.py # 335行 - 调度器+3个任务类
├── notifier.py              # 506行 - 企微推送(应用+Webhook)
└── wave_prediction_service.py
```

### 问题

| 问题 | 位置 | 影响 |
|------|------|------|
| **职责过多** | `dark_trade_stats.py` 承担5个角色 | 改一处怕崩全局 |
| **重复代码** | `_clean_code()` 在 stats 和 exporter 各一份 | 维护不一致 |
| **隐式耦合** | `push_dark_trade_stats()` 内部调用 `export_dark_trade_stats_excel()` | 无法独立控制 |
| **命名不一致** | exporter vs stats vs service | 认知负担 |
| **测试困难** | 推送/导出绑在一起 | 无法单独测试 |

---

## 目标结构

```
services/
├── __init__.py
├── dark_trade/                      # 暗盘模块（包）
│   ├── __init__.py                  # 公开 API
│   ├── utils.py                     # 共享工具函数
│   ├── calculator.py                # 统计计算
│   ├── formatter.py                 # 消息格式化
│   ├── exporter.py                  # Excel/CSV 导出
│   ├── pusher.py                    # 企业微信推送
│   ├── service.py                   # 后台服务（原 dark_trade_service.py）
│   └── cli.py                       # CLI 入口
├── scheduler/                       # 调度器模块（包）
│   ├── __init__.py
│   ├── base.py                      # ExportTask 协议
│   ├── tasks.py                     # 具体任务实现
│   └── scheduler.py                 # CloseExportScheduler
├── notifier.py                      # 保持不动（已够清晰）
└── wave_prediction_service.py       # 保持不动
```

---

## 详细设计

### 1. `dark_trade/utils.py` — 共享工具

```python
"""暗盘模块共享工具函数"""

from datetime import datetime, timedelta


def clean_code(code: str) -> str:
    """清理股票代码，去除市场前缀，统一6位"""
    for prefix in ("sh", "sz", "hk", "SH", "SZ", "HK"):
        if code.startswith(prefix):
            return code[len(prefix):]
    return code


def get_recent_trade_dates(n: int = 5) -> list[str]:
    """获取最近N个交易日日期列表（简单跳过周末）"""
    dates: list[str] = []
    current = datetime.now()
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates
```

### 2. `dark_trade/calculator.py` — 统计计算

```python
"""暗盘资金统计计算"""

from stock_monitor.services.dark_trade.utils import clean_code, get_recent_trade_dates
from stock_monitor.services.dark_trade_service import fetch_all_dark_trade, build_net_flow_index


def calculate_dark_trade_stats(
    watchlist_codes: list[str],
    history_days: int = 5,
) -> dict:
    """计算暗盘统计数据"""
    # ... 原有逻辑，但使用 utils 中的函数
```

### 3. `dark_trade/formatter.py` — 消息格式化

```python
"""暗盘统计消息格式化"""


def format_dark_trade_stats_message(stats: dict) -> str:
    """格式化暗盘统计推送消息"""
    # ... 原有逻辑
```

### 4. `dark_trade/exporter.py` — Excel 导出

```python
"""暗盘统计 Excel 导出"""

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats


def export_dark_trade_stats_excel(
    watchlist_codes: list[str],
    history_days: int = 5,
    output_dir: str | None = None,
) -> str | None:
    """导出暗盘统计到 Excel（筛选3日净流入>0且5日流入天数>3）"""
    # ... 原有逻辑
```

### 5. `dark_trade/pusher.py` — 推送

```python
"""暗盘统计推送到企业微信"""

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.services.dark_trade.formatter import format_dark_trade_stats_message


def push_dark_trade_stats(config: dict, watchlist_codes: list[str]) -> bool:
    """推送暗盘统计到企业微信"""
    # 只负责推送，不负责导出
    # ... 原有推送逻辑
```

### 6. `dark_trade/service.py` — 后台服务

直接迁移 `dark_trade_service.py`，更新导入路径。

### 7. `dark_trade/cli.py` — CLI 入口

```python
"""CLI 入口 - 暗盘资金统计"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(...)
    # ... 原有 CLI 逻辑
```

### 8. `dark_trade/__init__.py` — 公开 API

```python
"""暗盘资金统计模块"""

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.services.dark_trade.formatter import format_dark_trade_stats_message
from stock_monitor.services.dark_trade.exporter import export_dark_trade_stats_excel
from stock_monitor.services.dark_trade.pusher import push_dark_trade_stats

__all__ = [
    "calculate_dark_trade_stats",
    "format_dark_trade_stats_message",
    "export_dark_trade_stats_excel",
    "push_dark_trade_stats",
]
```

---

## 调用方更新

### `close_export_scheduler.py`

```python
# 旧
from stock_monitor.services.dark_trade_stats import ...
from stock_monitor.services.dark_trade_exporter import ...

# 新
from stock_monitor.services.dark_trade import (
    export_dark_trade_stats_excel,
)
from stock_monitor.services.dark_trade.exporter import export_dark_trade_csv
```

### `settings_dialog.py`

```python
# 旧
from stock_monitor.services.dark_trade_stats import (
    calculate_dark_trade_stats,
    export_dark_trade_stats_excel,
)

# 新
from stock_monitor.services.dark_trade import (
    calculate_dark_trade_stats,
    export_dark_trade_stats_excel,
)
```

### `main_window_view_model.py`

```python
# 旧
from stock_monitor.services.dark_trade_service import ...

# 新
from stock_monitor.services.dark_trade.service import ...
```

---

## 迁移步骤

| # | 步骤 | 风险 | 验证 |
|---|------|------|------|
| 1 | 创建 `services/dark_trade/` 包目录 | 低 | — |
| 2 | 提取 `utils.py`（clean_code, get_recent_trade_dates） | 低 | 单元测试 |
| 3 | 迁移 `calculator.py` | 中 | 单元测试 |
| 4 | 迁移 `formatter.py` | 低 | 单元测试 |
| 5 | 迁移 `exporter.py` | 中 | 单元测试 |
| 6 | 迁移 `pusher.py` | 中 | 单元测试 |
| 7 | 迁移 `service.py` | 高 | 集成测试 |
| 8 | 迁移 `cli.py` | 低 | CLI 测试 |
| 9 | 更新 `close_export_scheduler.py` 导入 | 中 | 调度器测试 |
| 10 | 更新 `settings_dialog.py` 导入 | 中 | UI 手动测试 |
| 11 | 更新 `main_window_view_model.py` 导入 | 中 | 启动测试 |
| 12 | 保留旧文件 30 天作为兼容层（可选） | 低 | — |

---

## 兼容层（可选）

如果担心一次性迁移风险，可以在旧文件中保留 re-export：

```python
# dark_trade_stats.py (兼容层，30天后删除)
"""⚠️ 已废弃，请使用 stock_monitor.services.dark_trade"""
from stock_monitor.services.dark_trade import (
    calculate_dark_trade_stats,
    format_dark_trade_stats_message,
    export_dark_trade_stats_excel,
    push_dark_trade_stats,
)
```

---

## 预期收益

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 最大文件行数 | 467 (exporter) | ~150 |
| 单文件职责数 | 5 (stats) | 1 |
| 重复代码 | 2处 `_clean_code()` | 1处 |
| 可独立测试 | ❌ 推送/导出耦合 | ✅ 完全解耦 |
| 新人理解成本 | 高（需读4个文件） | 低（按功能找文件） |

---

## 验证清单

- [ ] 所有单元测试通过
- [ ] 集成测试通过（真实数据计算）
- [ ] CLI 命令正常：`python -m stock_monitor.services.dark_trade.cli --codes sh600519`
- [ ] 设置界面"测试推送"按钮正常
- [ ] 设置界面"导出Excel"按钮正常
- [ ] 收盘调度器自动触发正常
- [ ] 企业微信推送正常
- [ ] Excel 文件生成在 `analysis_reports/` 目录
