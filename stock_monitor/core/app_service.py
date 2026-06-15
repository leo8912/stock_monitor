"""
Application Service 层
提供面向 UI 的业务用例编排，隔离 UI 与核心逻辑
"""

from typing import Optional

from stock_monitor.core.config_center import config_center
from stock_monitor.core.event_bus import Topics, event_bus
from stock_monitor.utils.logger import app_logger


class StockAppService:
    """
    股票业务应用服务

    职责：
    - 编排 UI 调用的核心业务逻辑
    - 协调多个服务/领域的交互
    - 处理事务和错误恢复
    """

    def __init__(self):
        self._dark_trade_service = None
        self._close_export_scheduler = None
        self._quant_worker = None

    def set_dark_trade_service(self, service) -> None:
        self._dark_trade_service = service

    def set_close_export_scheduler(self, scheduler) -> None:
        self._close_export_scheduler = scheduler

    def set_quant_worker(self, worker) -> None:
        self._quant_worker = worker

    # ── 暗盘数据 ──────────────────────────────────────────────────

    def get_dark_flow(self, code: str) -> Optional[tuple[float, int]]:
        """获取单只股票暗盘净流入数据"""
        if not self._dark_trade_service:
            return None
        return self._dark_trade_service.get_dark_flow(code)

    def refresh_dark_trade(self) -> None:
        """手动刷新暗盘数据"""
        if self._dark_trade_service:
            self._dark_trade_service.force_refresh()
            event_bus.publish(
                Topics.DARK_TRADE_UPDATED,
                data={"trigger": "manual"},
                source="StockAppService",
            )

    # ── 导出 ──────────────────────────────────────────────────────

    def export_dark_trade_excel(
        self, codes: list[str], output_dir: str
    ) -> Optional[str]:
        """导出暗盘数据到 Excel"""
        from stock_monitor.services.dark_trade_exporter import export_dark_trade_excel

        try:
            result = export_dark_trade_excel(codes, output_dir)
            if result:
                event_bus.publish(
                    Topics.EXPORT_COMPLETED,
                    data={"type": "dark_trade", "path": result},
                    source="StockAppService",
                )
            return result
        except Exception as e:
            app_logger.error(f"导出暗盘数据失败: {e}")
            return None

    def export_signals_excel(
        self, signals: list[dict], output_dir: str
    ) -> Optional[str]:
        """导出信号数据到 Excel"""
        from stock_monitor.services.dark_trade_exporter import export_to_excel

        try:
            result = export_to_excel(signals, output_dir)
            if result:
                event_bus.publish(
                    Topics.EXPORT_COMPLETED,
                    data={"type": "signals", "path": result},
                    source="StockAppService",
                )
            return result
        except Exception as e:
            app_logger.error(f"导出信号数据失败: {e}")
            return None

    # ── 量化扫描 ──────────────────────────────────────────────────

    def trigger_quant_scan(self, symbols: list[str] = None) -> None:
        """触发量化扫描"""
        if self._quant_worker:
            if symbols:
                self._quant_worker.set_symbols(symbols)
            self._quant_worker.start_worker()

    def stop_quant_scan(self) -> None:
        """停止量化扫描"""
        if self._quant_worker:
            self._quant_worker.stop_worker()

    # ── 配置 ──────────────────────────────────────────────────────

    def update_stocks(self, stocks: list[str]) -> bool:
        """更新自选股列表"""
        return config_center.set(ConfigKeys.USER_STOCKS, stocks)

    def get_stocks(self) -> list[str]:
        """获取自选股列表"""
        return config_center.user_stocks


# 需要导入 ConfigKeys
from stock_monitor.utils.config_helper import ConfigKeys

# 全局应用服务实例
stock_app_service = StockAppService()
