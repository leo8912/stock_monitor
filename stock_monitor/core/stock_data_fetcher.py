"""兼容旧路径: 从 core.data 重新导出 StockDataFetcher。"""

from stock_monitor.core.data.stock_data_fetcher import StockDataFetcher

__all__ = ["StockDataFetcher"]
