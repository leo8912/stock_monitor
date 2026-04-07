"""兼容旧路径: 从 core.data 重新导出 StockDataValidator。"""

from stock_monitor.core.data.stock_data_validator import StockDataValidator

__all__ = ["StockDataValidator"]
