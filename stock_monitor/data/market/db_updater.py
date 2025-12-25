"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""

import threading
import time

from stock_monitor.data.stock.stock_updater import (
    update_stock_database as _core_update_db,
)
from stock_monitor.utils.logger import app_logger


def update_stock_database() -> bool:
    """
    更新本地股票数据库

    Returns:
        bool: 更新是否成功
    """
    # 直接调用核心更新逻辑，避免双重获取
    return _core_update_db()


def get_stock_list() -> list[dict[str, str]]:
    """
    获取股票列表，从本地数据库读取

    Returns:
        List[Dict[str, str]]: 股票列表
    """
    try:
        from stock_monitor.data.stock.stock_db import stock_db

        return stock_db.get_all_stocks()
    except Exception as e:
        app_logger.error(f"无法从本地数据库加载股票数据: {e}")
        # 返回空列表
        return []


def preload_popular_stocks_data() -> None:
    """
    预加载热门股票数据到缓存中
    这个函数会在市场开盘前运行，预热缓存
    """
    try:
        app_logger.info("开始预加载热门股票数据...")

        # 热门股票列表（包括主要指数和一些热门个股）
        popular_stocks = [
            "sh000001",  # 上证指数
            "sz399001",  # 深证成指
            "sh000300",  # 沪深300
            "sz399006",  # 创业板指
            "sh600036",  # 招商银行
            "sh600519",  # 贵州茅台
            "sz000858",  # 五粮液
            "sz000001",  # 平安银行
            "sh000000",  # 上证指数（备用）
            "hk00700",  # 腾讯控股
            "hk09988",  # 阿里巴巴
            "hk03690",  # 美团
        ]

        from stock_monitor.core.stock_manager import stock_manager

        # 使用stock_manager获取数据，这会自动触发缓存
        stock_manager.get_stock_list_data(popular_stocks)

        app_logger.info(f"热门股票数据预加载完成，共 {len(popular_stocks)} 只股票")

    except Exception as e:
        app_logger.error(f"预加载热门股票数据时出错: {e}")


def start_preload_scheduler() -> None:
    """
    启动预加载调度器
    在市场开盘前（9:25）自动预加载热门股票数据
    """

    def scheduler():
        while True:
            try:
                import datetime

                # 获取当前时间
                now = datetime.datetime.now()
                # 计算下次预加载时间（今天或明天的9:25）
                next_preload = now.replace(hour=9, minute=25, second=0, microsecond=0)
                if now >= next_preload:
                    # 如果当前时间已经超过今天的9:25，则设置为明天的9:25
                    next_preload += datetime.timedelta(days=1)

                # 计算睡眠时间
                sleep_seconds = (next_preload - now).total_seconds()
                app_logger.info(
                    f"预加载调度器: 下次预加载将在 {next_preload} 执行，睡眠 {sleep_seconds} 秒"
                )

                # 睡眠直到下次预加载时间
                time.sleep(sleep_seconds)

                # 执行预加载
                preload_popular_stocks_data()

            except Exception as e:
                app_logger.error(f"预加载调度器出错: {e}")
                # 出错时等待1小时再重试
                time.sleep(3600)

    # 在独立线程中运行调度器
    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    app_logger.info("预加载调度器已启动")


if __name__ == "__main__":
    # 测试更新功能
    success = update_stock_database()
    if success:
        app_logger.info("股票数据库更新成功")
    else:
        app_logger.error("股票数据库更新失败")
