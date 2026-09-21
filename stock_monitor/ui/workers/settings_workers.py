"""设置对话框使用的后台工作线程集合。

Phase A 结构治理（T13）：把原先散落在 ``settings_dialog.py`` 中的 6 个 QThread
子类抽取到独立模块，使对话框文件专注于 UI 编排。网络能力统一收敛到
``NotifierService``（去重），因此本模块不再依赖 ``requests``。

``settings_dialog`` 对这些类做 re-export，保持既有导入路径（含测试）兼容。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class TaskThread(QThread):
    """设置页一次性后台任务的统一基类。

    长生命周期 worker 继续使用专用 QThread；设置页的网络与导出操作仅需一个
    执行入口和一致的异常转换，避免每个小任务重复实现线程模板。
    """

    failed = pyqtSignal(str)

    def _run_task(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        try:
            on_success(task())
        except Exception as exc:
            (on_error or self.failed.emit)(str(exc))


class UpdateCheckThread(TaskThread):
    """更新检查线程（从 check_for_updates 方法提取）"""

    finished_check = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def run(self) -> None:
        """在后台线程执行更新检查并发出结果/错误信号。"""

        def task():
            from stock_monitor.core.updater import app_updater

            return app_updater.check_for_updates()

        self._run_task(task, self.finished_check.emit, self.error_occurred.emit)


class ExcelExportThread(TaskThread):
    """Excel 导出后台线程"""

    export_finished = pyqtSignal(bool, str)

    def __init__(self, watchlist_codes: list, parent=None) -> None:
        """初始化 Excel 导出线程。

        Args:
            watchlist_codes: 需要导出的自选股代码列表。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._watchlist_codes = watchlist_codes

    def run(self) -> None:
        """在后台线程导出 Excel 并发出完成信号（成功/失败+信息）。"""

        def task():
            from scripts.reporting.export_stocks_to_excel import export_to_excel

            output_path = "analysis_reports/stock_export_report.xlsx"
            export_to_excel(
                output_path=output_path,
                include_history=True,
                history_symbols=self._watchlist_codes,
            )
            return output_path

        self._run_task(
            task,
            lambda output_path: self.export_finished.emit(True, output_path),
            lambda error: self.export_finished.emit(False, error),
        )


class TestAppThread(TaskThread):
    """企业应用推送测试线程（网络逻辑委托 NotifierService，避免重复实现）。"""

    test_finished = pyqtSignal(dict)

    def __init__(self, corp_id: str, secret: str, agent_id: str, parent=None) -> None:
        """初始化企业应用推送测试线程。

        Args:
            corp_id: 企业微信 CorpID。
            secret: 应用 Secret。
            agent_id: 应用 AgentID。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._corp_id = corp_id
        self._secret = secret
        self._agent_id = agent_id

    def run(self) -> None:
        """在后台线程调用 NotifierService 发送测试消息，完成后发出结果信号。"""

        def task():
            from stock_monitor.services.notifier import NotifierService

            return NotifierService.test_app_push(
                self._corp_id, self._secret, self._agent_id
            )

        self._run_task(
            task,
            self.test_finished.emit,
            lambda error: self.test_finished.emit(
                {"success": False, "error": error, "response": None}
            ),
        )


class DarkTradeExportThread(TaskThread):
    """暗盘数据导出后台线程"""

    export_finished = pyqtSignal(bool, str)

    def __init__(self, watchlist_codes: list, parent=None) -> None:
        """初始化暗盘数据导出线程。

        Args:
            watchlist_codes: 需要导出的自选股代码列表。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._watchlist_codes = watchlist_codes

    def run(self) -> None:
        """在后台线程导出暗盘 CSV 并发出完成信号。"""

        def task():
            from stock_monitor.services.dark_trade_exporter import (
                export_dark_trade_csv,
            )
            from stock_monitor.utils.logger import app_logger

            app_logger.info("[DarkExport] 手动触发暗盘数据导出...")
            output_path = export_dark_trade_csv(
                watchlist_codes=self._watchlist_codes,
                history_days=5,
            )
            return (
                f"暗盘资金数据已成功导出！\n\n"
                f"保存位置：\n{output_path}\n\n"
                f"包含全市场暗盘+明盘行情数据",
            )

        self._run_task(
            task,
            lambda message: self.export_finished.emit(True, message),
            lambda error: self.export_finished.emit(
                False, f"导出暗盘数据时发生异常：\n{error}"
            ),
        )


class DarkTradeStatsPushThread(TaskThread):
    """暗盘统计推送后台线程"""

    push_finished = pyqtSignal(bool, str)

    def __init__(self, watchlist_codes: list, parent=None) -> None:
        """初始化暗盘统计推送线程。

        Args:
            watchlist_codes: 需要统计的自选股代码列表。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._watchlist_codes = watchlist_codes

    def run(self) -> None:
        """在后台线程计算暗盘统计并推送，完成后发出结果信号。"""

        def task():
            from stock_monitor.core.config_center import config_center
            from stock_monitor.services.dark_trade import (
                calculate_dark_trade_stats,
                format_dark_trade_stats_message,
            )
            from stock_monitor.utils.logger import app_logger

            app_logger.info("[DarkStats] 手动触发暗盘统计推送...")

            # 计算统计
            stats = calculate_dark_trade_stats(self._watchlist_codes, history_days=5)

            if not stats.get("market_summary"):
                return False, "无统计数据（可能非交易时段或网络异常）"

            # 格式化消息
            message = format_dark_trade_stats_message(stats)

            # 推送
            from stock_monitor.services.notifier import NotifierService

            title = "📊 暗盘资金统计"
            success = NotifierService.dispatch_custom_message(
                config_center.snapshot(), title, message
            )

            if success:
                return True, "暗盘统计推送成功！\n\n" + message
            return False, "暗盘统计推送失败，请检查企业微信配置"

        self._run_task(
            task,
            lambda result: self.push_finished.emit(*result),
            lambda error: self.push_finished.emit(
                False, f"推送暗盘统计时发生异常：\n{error}"
            ),
        )


class DarkTradeStatsExcelExportThread(TaskThread):
    """暗盘统计 Excel 导出后台线程。

    取代早期「 ``threading.Thread`` + 从子线程调用 ``QTimer.singleShot``」的写法：
    子线程没有 Qt 事件循环，``singleShot`` 回调永远不会执行，导致完成提示不弹、
    WaitCursor 无法恢复。改用 QThread 信号（自动排队回主线程）驱动 UI 回调。
    """

    export_finished = pyqtSignal(bool, str)

    def __init__(self, watchlist_codes: list, parent=None) -> None:
        """初始化暗盘统计 Excel 导出线程。

        Args:
            watchlist_codes: 需要导出的自选股代码列表。
            parent: QObject 父对象。
        """
        super().__init__(parent)
        self._watchlist_codes = watchlist_codes

    def run(self) -> None:
        """在后台线程导出暗盘统计 Excel 并发出完成信号。"""

        def task():
            from stock_monitor.services.dark_trade.exporter import (
                export_dark_trade_stats_excel,
            )

            excel_path = export_dark_trade_stats_excel(self._watchlist_codes)
            return str(excel_path) if excel_path else ""

        self._run_task(
            task,
            lambda path: self.export_finished.emit(bool(path), path),
            lambda error: self.export_finished.emit(False, error),
        )
