"""
市场状态管理核心模块
负责处理市场状态相关的业务逻辑

该模块包含MarketManager类，用于管理市场状态和数据库更新。
"""

import time
import datetime
from typing import Optional
from stock_monitor.utils.logger import app_logger
from stock_monitor.data.market.updater import update_stock_database


class MarketManager:
    """
    市场管理器，负责处理市场状态和数据库更新的核心业务逻辑
    """
    
    def __init__(self):
        self.last_update_time: Optional[datetime.datetime] = None
    
    def update_database_on_startup(self) -> None:
        """
        在应用启动时更新股票数据库
        """
        def update_database():
            try:
                app_logger.info("应用启动时更新股票数据库...")
                # 添加网络连接检查和延迟，确保网络就绪
                time.sleep(10)  # 增加到10秒等待网络连接初始化
                success = update_stock_database()
                if success:
                    app_logger.info("启动时股票数据库更新完成")
                    self.last_update_time = datetime.datetime.now()
                else:
                    app_logger.warning("启动时股票数据库更新失败")
            except Exception as e:
                app_logger.error(f"启动时数据库更新出错: {e}")
        
        # 在后台线程中执行数据库更新，避免阻塞UI
        import threading
        update_thread = threading.Thread(target=update_database, daemon=True)
        update_thread.start()
    
    def start_database_update_scheduler(self) -> None:
        """
        启动数据库更新调度器
        """
        import threading
        from stock_monitor.data.market.updater import start_preload_scheduler
        self._database_update_thread = threading.Thread(target=self._database_update_loop, daemon=True)
        self._database_update_thread.start()
        
        # 启动缓存预加载调度器
        start_preload_scheduler()
    
    def _database_update_loop(self) -> None:
        """
        数据库更新循环 - 每天更新一次股票数据库
        """
        # 等待应用启动完成
        time.sleep(10)
        
        while True:
            try:
                # 检查是否是凌晨时段（2:00-4:00之间）
                now = datetime.datetime.now()
                if now.hour >= 2 and now.hour < 4:
                    app_logger.info("开始更新股票数据库...")
                    success = update_stock_database()
                    if success:
                        app_logger.info("股票数据库更新完成")
                        self.last_update_time = now
                    else:
                        app_logger.warning("股票数据库更新失败")
                    
                    # 等待到明天同一时间
                    tomorrow = now + datetime.timedelta(days=1)
                    tomorrow_update = tomorrow.replace(hour=3, minute=0, second=0, microsecond=0)
                    sleep_seconds = (tomorrow_update - now).total_seconds()
                    time.sleep(sleep_seconds)
                else:
                    # 每小时检查一次时间
                    time.sleep(3600)
            except Exception as e:
                app_logger.error(f"数据库更新循环出错: {e}")
                time.sleep(3600)  # 出错后等待1小时再重试