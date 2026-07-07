"""
收盘自动导出调度器
负责在每天收盘时(15:05)自动触发数据抓取和导出任务
"""

import threading
from datetime import datetime
from datetime import time as dtime
from pathlib import Path
from typing import Any, Protocol

from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger


class ExportTask(Protocol):
    """收盘导出任务协议"""

    @property
    def name(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    def execute(self) -> Any: ...

    def set_enabled(self, enabled: bool) -> None: ...


class DarkTradeExcelTask:
    """暗盘资金Excel导出任务"""

    def __init__(self) -> None:
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
        from stock_monitor.services.dark_trade_exporter import (
            export_dark_trade_excel,
        )

        try:
            dark_file = export_dark_trade_excel(watchlist_codes=[])
            app_logger.info(f"[CloseExportScheduler] 暗盘数据已导出: {dark_file}")
            return str(dark_file)
        except Exception as e:
            app_logger.error(f"[CloseExportScheduler] 暗盘数据导出失败: {e}")
            return None


class StockIndicatorsTask:
    """自选股技术指标导出任务"""

    def __init__(self) -> None:
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

    def __init__(self) -> None:
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
            result = push_dark_trade_stats(config_center.snapshot(), user_stocks)
            if result:
                app_logger.info("[CloseExportScheduler] 暗盘统计推送已触发")
            else:
                app_logger.warning("[CloseExportScheduler] 暗盘统计推送返回失败")
            return result
        except Exception as e:
            app_logger.error(f"[CloseExportScheduler] 暗盘统计推送失败: {e}")
            return False


class CloseExportScheduler(QtCore.QThread):
    """
    收盘自动导出调度器线程

    功能：
    1. 每天15:05-15:30之间触发一次收盘数据导出
    2. 导出暗盘资金数据Excel
    3. 导出自选股技术指标Excel
    4. 保存全A股行情快照（可选）

    Signals:
        export_started: 导出任务开始
        export_completed: 导出任务完成（携带导出文件路径列表）
        export_failed: 导出任务失败（携带错误信息）
    """

    export_started = QtCore.pyqtSignal()
    export_completed = QtCore.pyqtSignal(list)  # 导出文件路径列表
    export_failed = QtCore.pyqtSignal(str)  # 错误信息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._enabled = False
        self._last_export_date = ""
        self._export_time_window_start = dtime(15, 5)  # 15:05
        self._export_time_window_end = dtime(15, 30)  # 15:30
        self._check_interval_ms = 60000  # 每60秒检查一次
        self._export_lock = threading.Lock()
        # 注册默认任务
        self._tasks: list[ExportTask] = [
            DarkTradeExcelTask(),
            StockIndicatorsTask(),
            DarkTradeStatsTask(),
        ]

    def enable(self):
        """启用自动导出"""
        self._enabled = True
        app_logger.info("[CloseExportScheduler] 自动导出已启用")

    def disable(self):
        """禁用自动导出"""
        self._enabled = False
        app_logger.info("[CloseExportScheduler] 自动导出已禁用")

    def set_enabled(self, enabled: bool):
        """设置是否启用"""
        if enabled:
            self.enable()
        else:
            self.disable()

    def is_enabled(self) -> bool:
        """是否启用"""
        return self._enabled

    def register_task(self, task: ExportTask) -> None:
        """注册导出任务"""
        self._tasks.append(task)
        app_logger.info(f"[CloseExportScheduler] 注册任务: {task.name}")

    def get_tasks(self) -> list[ExportTask]:
        """获取所有已注册任务"""
        return list(self._tasks)

    def _should_export_today(self) -> bool:
        """判断今天是否应该执行导出"""
        now = datetime.now()

        # 周末不执行
        if now.weekday() >= 5:
            return False

        # 检查是否在当前时间窗口内
        t = now.time()
        if not (self._export_time_window_start <= t <= self._export_time_window_end):
            return False

        # 检查今天是否已经执行过
        today_str = now.strftime("%Y%m%d")
        if self._last_export_date == today_str:
            return False

        return True

    def _mark_exported(self):
        """标记今天已执行"""
        self._last_export_date = datetime.now().strftime("%Y%m%d")

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
                    app_logger.error(
                        f"[CloseExportScheduler] 任务 {task.name} 异常: {e}"
                    )

            # 标记今天已执行
            self._mark_exported()

            # 发送完成信号
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

    def run(self):
        """线程主循环"""
        app_logger.info("[CloseExportScheduler] 调度器启动")

        while self._running:
            try:
                if self._enabled and self._should_export_today():
                    app_logger.info(
                        "[CloseExportScheduler] 检测到收盘时段，开始执行自动导出..."
                    )
                    self._execute_export()

            except Exception as e:
                app_logger.error(f"[CloseExportScheduler] 主循环异常: {e}")

            # 休眠等待下一次检查
            for _ in range(self._check_interval_ms // 100):
                if not self._running:
                    break
                self.msleep(100)

        app_logger.info("[CloseExportScheduler] 调度器已停止")

    def start_scheduler(self):
        """启动调度器"""
        if not self.isRunning():
            self._running = True
            self.start()
            app_logger.info("[CloseExportScheduler] 调度器线程已启动")

    def stop_scheduler(self):
        """停止调度器"""
        self._running = False
        self.wait(3000)
        app_logger.info("[CloseExportScheduler] 调度器线程已停止")

    def trigger_now(self, task_name: str | None = None):
        """立即触发一次导出（用于测试）

        Args:
            task_name: 指定任务名则只触发该任务，None则触发所有任务
        """
        app_logger.info(
            f"[CloseExportScheduler] 手动触发导出测试 (task={task_name})..."
        )
        self._execute_export(task_name=task_name)


# 全局单例
_scheduler_instance = None
_scheduler_lock = threading.Lock()


def get_close_export_scheduler() -> CloseExportScheduler:
    """获取全局调度器实例（懒初始化）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        with _scheduler_lock:
            if _scheduler_instance is None:
                _scheduler_instance = CloseExportScheduler()
    return _scheduler_instance
