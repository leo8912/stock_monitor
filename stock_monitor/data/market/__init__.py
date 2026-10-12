"""Market data module"""

from stock_monitor.core.market.market_manager import market_manager

from .db_updater import update_stock_database
from .quotation import get_name_by_code, get_quotation_engine

# 使用 MarketManager 单例实例绑定 is_market_open（该方法是普通实例方法，
# 直接取类属性 MarketManager.is_market_open 会因缺少 self 而在调用时抛 TypeError）
is_market_open = market_manager.is_market_open

__all__ = [
    "get_quotation_engine",
    "is_market_open",
    "get_name_by_code",
    "update_stock_database",
]
