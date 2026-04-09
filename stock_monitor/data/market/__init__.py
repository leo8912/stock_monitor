"""Market data module"""

# 导入公共函数，统一接口
from stock_monitor.core.market.market_manager import MarketManager

from .db_updater import get_stock_list, update_stock_database
from .quotation import get_name_by_code, get_quotation_engine

# 使用 MarketManager 的 is_market_open 统一开市时间判断
is_market_open = MarketManager.is_market_open

__all__ = [
    "get_quotation_engine",
    "is_market_open",
    "get_name_by_code",
    "update_stock_database",
    "get_stock_list",
]
