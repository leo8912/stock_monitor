"""
股票数据处理模块
用于加载和处理股票基础数据
"""

from typing import Any

from stock_monitor.utils.logger import app_logger


def load_stock_data() -> list[dict[str, Any]]:
    """
    加载股票基础数据

    从SQLite数据库加载股票基础数据。

    Returns:
        List[Dict[str, Any]]: 股票数据列表，每个元素包含 'code' 和 'name' 字段
    """
    # 从SQLite数据库加载股票数据
    from stock_monitor.core.config.container import container
    from stock_monitor.data.stock.stock_db import StockDatabase

    stock_db = container.get(StockDatabase)

    # 获取所有股票数据
    a_stocks = stock_db.get_stocks_by_market_type("A")
    index_stocks = stock_db.get_stocks_by_market_type("INDEX")
    hk_stocks = stock_db.get_stocks_by_market_type("HK")

    all_stocks = a_stocks + index_stocks + hk_stocks
    app_logger.debug(f"从SQLite数据库加载股票基础数据成功，共{len(all_stocks)}条记录")
    return all_stocks
