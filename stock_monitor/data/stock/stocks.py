"""
股票数据处理模块
用于加载和处理股票基础数据
"""

from typing import Any, Optional

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


def format_stock_code(code: str) -> Optional[str]:
    """
    格式化股票代码，确保正确的前缀

    将6位数字股票代码转换为带交易所前缀的标准格式，或验证已带前缀的代码是否有效。

    Args:
        code (str): 股票代码，可以是6位数字或已带前缀的8位代码

    Returns:
        Optional[str]: 格式化后的股票代码，如果输入无效则返回None
    """
    # 使用工具函数处理股票代码格式化
    from stock_monitor.utils.helpers import format_stock_code

    return format_stock_code(code)
