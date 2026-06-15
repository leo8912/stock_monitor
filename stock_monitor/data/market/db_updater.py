"""
股票数据库更新模块
负责从网络获取最新的股票数据并更新本地 SQLite 数据库
"""

from stock_monitor.data.stock.stock_updater import (
    update_stock_database as _core_update_db,
)


def update_stock_database() -> bool:
    """
    更新本地股票数据库

    Returns:
        bool: 更新是否成功
    """
    return _core_update_db()
