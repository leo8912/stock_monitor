"""
后台刷新工作线程模块
负责处理股票数据的后台刷新逻辑
"""

import threading
import time
from typing import List, Dict, Any, Callable
from stock_monitor.utils.logger import app_logger
from stock_monitor.config.manager import is_market_open
from stock_monitor.core.stock_service import stock_data_service
from stock_monitor.utils.stock_utils import StockCodeProcessor
from stock_monitor.core.data_change_detector import DataChangeDetector


class RefreshWorker:
    """后台刷新工作线程"""
    
    def __init__(self, update_callback: Callable, error_callback: Callable):
        """
        初始化刷新工作线程
        
        Args:
            update_callback: UI更新回调函数
            error_callback: 错误处理回调函数
        """
        self.update_callback = update_callback
        self.error_callback = error_callback
        self._stop_event = threading.Event()
        self.refresh_interval = 5
        self.current_user_stocks: List[str] = []
        self._lock = threading.Lock()  # 添加锁保护并发访问
        self._thread = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._processor = StockCodeProcessor()
        self._data_change_detector = DataChangeDetector()
        
    def start(self, user_stocks: List[str], refresh_interval: int):
        """
        启动刷新线程
        
        Args:
            user_stocks: 用户股票列表
            refresh_interval: 刷新间隔（秒）
        """
        self.current_user_stocks = user_stocks
        self.refresh_interval = refresh_interval
        
        if self._thread and self._thread.is_alive():
            self.stop()
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._thread.start()
        app_logger.info("后台刷新线程已启动")
        app_logger.debug(f"刷新间隔: {self.refresh_interval}秒")
        
    def stop(self):
        """停止刷新线程"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        app_logger.info("后台刷新线程已停止")
        
    def update_stocks(self, user_stocks: List[str]):
        """
        更新用户股票列表
        
        Args:
            user_stocks: 新的用户股票列表
        """
        with self._lock:
            self.current_user_stocks = user_stocks
        app_logger.info(f"刷新线程股票列表已更新: {user_stocks}")
        
    def update_interval(self, refresh_interval: int):
        """
        更新刷新间隔
        
        Args:
            refresh_interval: 新的刷新间隔（秒）
        """
        with self._lock:
            self.refresh_interval = refresh_interval
        app_logger.info(f"刷新线程间隔已更新: {refresh_interval}")
        
    def _should_wait_before_next_refresh(self, local_user_stocks: List[str]) -> bool:
        """
        检查是否需要等待下次刷新
        
        Args:
            local_user_stocks: 当前用户股票列表
            
        Returns:
            bool: 是否需要等待
        """
        if not local_user_stocks:
            # 如果没有股票，等待下次刷新
            sleep_time = self.refresh_interval if is_market_open() else 60
            app_logger.debug(f"无自选股数据，下次刷新间隔: {sleep_time}秒")
            if self._stop_event.wait(sleep_time):
                return True
        return False
        
    def _refresh_loop(self):
        """刷新循环"""
        # 减少启动延迟，给系统网络连接一些初始化时间
        app_logger.info("后台刷新线程启动，等待1秒初始化网络连接...")
        if self._stop_event.wait(1):
            return
            
        # 使用锁保护访问共享变量
        with self._lock:
            local_user_stocks = self.current_user_stocks[:]
            local_refresh_interval = self.refresh_interval
        
        while not self._stop_event.is_set():
            try:
                # 检查是否有配置更新
                with self._lock:
                    if (local_user_stocks != self.current_user_stocks or 
                        local_refresh_interval != self.refresh_interval):
                        local_user_stocks = self.current_user_stocks[:]
                        local_refresh_interval = self.refresh_interval
                        app_logger.info(f"刷新线程检测到配置变更，更新本地缓存: 股票={local_user_stocks}, 间隔={local_refresh_interval}")
                
                # 检查是否有需要更新的数据
                app_logger.debug(f"当前需要刷新的股票: {local_user_stocks}")
                if self._should_wait_before_next_refresh(local_user_stocks):
                    break
                
                # 直接获取所有股票数据，不使用缓存
                app_logger.debug(f"需要获取 {len(local_user_stocks)} 只股票数据")
                data_dict = stock_data_service.get_multiple_stocks_data(local_user_stocks)
                
                # 统计失败数量
                failed_count = sum(1 for data in data_dict.values() if data is None)
                
                stocks = stock_data_service.process_stock_data(data_dict, local_user_stocks)
                
                # 检查数据是否发生变化，只在有变化时更新UI
                # 但在应用刚启动时强制更新一次UI，确保数据显示
                force_update = not hasattr(self, '_initial_update_done')
                if force_update or self._data_change_detector.has_stock_data_changed(stocks):
                    app_logger.debug("检测到股票数据变化或首次更新，更新UI")
                    # 更新缓存数据
                    self._data_change_detector.update_last_stock_data(stocks)
                    # 标记已完成首次更新
                    if not hasattr(self, '_initial_update_done'):
                        self._initial_update_done = True
                    # 调用更新回调
                    self.update_callback(stocks, failed_count == len(local_user_stocks) and len(local_user_stocks) > 0)
                else:
                    app_logger.debug("股票数据无变化，跳过UI更新")
                    
                self._consecutive_failures = 0  # 重置失败计数
                
                # 记录成功更新的信息
                success_count = len(stocks) - failed_count
                app_logger.info(f"股票数据更新完成: 成功 {success_count} 只，失败 {failed_count} 只")
                
                # 根据开市状态决定刷新间隔
                sleep_time = local_refresh_interval if is_market_open() else 60
                app_logger.debug(f"下次刷新间隔: {sleep_time}秒")
                # 确保睡眠时间非负
                if sleep_time < 0:
                    sleep_time = 5  # 默认5秒
                if self._stop_event.wait(sleep_time):
                    break
                    
            except Exception as e:
                app_logger.error(f'行情刷新异常: {e}')
                self._consecutive_failures += 1
                
                # 如果连续失败多次，发送错误信息到UI
                if self._consecutive_failures >= self._max_consecutive_failures:
                    app_logger.error(f"连续{self._max_consecutive_failures}次刷新失败")
                    self.error_callback()
                    self._consecutive_failures = 0  # 重置失败计数
                    
                # 出错后等待一段时间再继续
                if self._stop_event.wait(5):
                    break