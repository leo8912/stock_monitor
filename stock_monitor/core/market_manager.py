"""兼容旧路径: 从 core.market 重新导出 MarketManager。"""

from stock_monitor.core.market.market_manager import (
    MarketManager,
    MarketSentiment,
    market_manager,
)

__all__ = ["MarketManager", "MarketSentiment", "market_manager"]
