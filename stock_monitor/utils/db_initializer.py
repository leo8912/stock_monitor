"""
数据库初始化模块
用于初始化SQLite数据库
"""

from stock_monitor.utils.logger import app_logger
from stock_monitor.data.stock.stock_db import stock_db

def initialize_database_schema():
    """
    初始化数据库表结构
    """
    try:
        # 检查数据库是否已经有数据
        stock_count = stock_db.get_all_stocks_count()
        
        if stock_count == 0:
            app_logger.info("数据库为空，需要手动导入数据或检查数据源")
        else:
            app_logger.info(f"数据库已有 {stock_count} 条股票数据")
        return True
        
    except Exception as e:
        app_logger.error(f"初始化数据库失败: {e}")
        return False

def initialize_database():
    """
    初始化数据库
    """
    try:
        # 检查数据库是否已经有数据
        stock_count = stock_db.get_all_stocks_count()
        
        if stock_count == 0:
            app_logger.info("数据库为空，需要手动导入数据或检查数据源")
        else:
            app_logger.info(f"数据库已有 {stock_count} 条股票数据")
        return True
        
    except Exception as e:
        app_logger.error(f"初始化数据库失败: {e}")
        return False

if __name__ == "__main__":
    # 可以直接运行此脚本来初始化数据库
    initialize_database()