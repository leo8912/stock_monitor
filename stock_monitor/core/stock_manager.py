"""兼容旧路径"""

from stock_monitor.core.market.stock_manager import (
    StockManager,
    get_dynamic_lru_cache_size,
    stock_manager,
)

__all__ = ["StockManager", "stock_manager", "get_dynamic_lru_cache_size"]
