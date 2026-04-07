"""兼容旧路径: 从 core.data 重新导出 StockDataProcessor。"""

from stock_monitor.core.data.stock_data_processor import StockDataProcessor

__all__ = ["StockDataProcessor"]
