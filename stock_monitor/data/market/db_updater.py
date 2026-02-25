"""
股票数据库更新模块
负责定期从网络获取最新的股票数据并更新本地 SQLite 数据库
"""


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
        from stock_monitor.core.container import container
        from stock_monitor.data.stock.stock_db import StockDatabase

        stock_db = container.get(StockDatabase)

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

    import datetime

    from PyQt6.QtCore import QTimer

    from stock_monitor.utils.logger import app_logger

    app_logger.info("准备启动预加载调度器...")

    # 因为这个函数可能不是在 main_window 内调用（而是在整个 app 生命周期内）
    # 但由于它在主进入点被触发，我们可以创建并寄宿一个全局的 QTimer

    # 避免垃圾回收
    if getattr(start_preload_scheduler, "_timer", None) is not None:
        start_preload_scheduler._timer.stop()

    start_preload_scheduler._timer = QTimer()

    def check_and_preload():
        try:
            now = datetime.datetime.now()
            # 检查现在是不是在 9:25:00 到 9:25:59 之间
            if now.hour == 9 and now.minute == 25:
                # 只有当今天还没预加载过时才执行
                last_preload_date = getattr(check_and_preload, "_last_date", None)
                if last_preload_date != now.date():
                    app_logger.info("到达预定时间 9:25，执行预加载")
                    preload_popular_stocks_data()
                    check_and_preload._last_date = now.date()
        except Exception as e:
            app_logger.error(f"预加载调度器检查出错: {e}")

    # 每分钟检查一次
    start_preload_scheduler._timer.timeout.connect(check_and_preload)
    start_preload_scheduler._timer.start(60 * 1000)
    app_logger.info("预加载调度器已作为 QTimer 启动")


if __name__ == "__main__":
    # 测试更新功能
    success = update_stock_database()
    if success:
        app_logger.info("股票数据库更新成功")
    else:
        app_logger.error("股票数据库更新失败")
