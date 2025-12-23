"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""

from pypinyin import Style, lazy_pinyin

from stock_monitor.data.fetcher import stock_fetcher
from stock_monitor.data.stock.stock_db import stock_db
from stock_monitor.utils.logger import app_logger


def update_stock_database() -> bool:
    """
    更新本地股票数据库

    Returns:
        bool: 更新是否成功
    """
    return incremental_update_stock_database()


def incremental_update_stock_database() -> bool:
    """
    增量更新本地股票数据库 (包含拼音生成)

    Returns:
        bool: 更新是否成功
    """
    try:
        # 1. 获取最新的股票数据
        stocks_data = stock_fetcher.fetch_all_stocks()

        if not stocks_data:
            app_logger.warning("未获取到股票数据，取消更新")
            return False

        # 2. 按代码排序
        stocks_data.sort(key=lambda x: x["code"])

        # 3. 为股票数据添加拼音信息
        app_logger.info("开始为股票数据添加拼音信息...")
        for stock in stocks_data:
            name = stock["name"]
            # 去除*ST、ST等前缀，避免影响拼音识别
            base = name.replace("*", "").replace("ST", "").replace(" ", "")
            # 生成全拼
            full_pinyin = "".join(lazy_pinyin(base))
            # 生成首字母缩写
            abbr = "".join(lazy_pinyin(base, style=Style.FIRST_LETTER))
            stock["pinyin"] = full_pinyin.lower()
            stock["abbr"] = abbr.lower()

        app_logger.info("拼音信息处理完成")

        # 4. 批量插入/更新数据库
        app_logger.info(f"开始更新股票数据库，共 {len(stocks_data)} 条记录...")
        count = stock_db.insert_stocks(stocks_data)
        app_logger.info(f"股票数据库更新完成，共处理/更新 {count} 条记录")

        # 5. 更新成功后保存时间戳
        try:
            import time

            from stock_monitor.config.manager import ConfigManager

            config_manager = ConfigManager()
            config_manager.set("last_db_update", time.time())
            app_logger.info("数据库更新时间戳已保存")
        except Exception as e:
            app_logger.warning(f"保存数据库更新时间戳失败: {e}")

        return True
    except Exception as e:
        app_logger.error(f"更新股票数据库失败: {e}")
        return False
