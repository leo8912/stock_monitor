"""
数据处理层 (Data Layer)

职责:
- 数据获取 (从多源: mootdx, akshare)
- 数据预处理和转换
- 数据有效性验证
- 缓存和持久化

模块包含:
- fetcher.py: 数据获取器
- processor.py: 数据处理器
- validator.py: 数据验证器
"""

from .stock_data_fetcher import StockDataFetcher
from .stock_data_processor import StockDataProcessor
from .stock_data_validator import StockDataValidator

__all__ = ["StockDataFetcher", "StockDataProcessor", "StockDataValidator"]
