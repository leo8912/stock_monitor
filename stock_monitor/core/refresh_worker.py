from PyQt6 import QtCore
import time
from typing import List, Dict, Any, Callable
from stock_monitor.utils.logger import app_logger
from stock_monitor.config.manager import is_market_open
from stock_monitor.utils.logger import app_logger
from stock_monitor.config.manager import is_market_open
from stock_monitor.utils.stock_utils import StockCodeProcessor


class RefreshWorker(QtCore.QThread):
    """
    后台刷新工作线程
    
    负责在后台定期获取股票数据并更新UI。
    使用独立线程避免阻塞主UI线程。
    
    Signals:
        data_updated: 数据更新信号，参数为(股票列表, 是否全部失败)
        refresh_error: 刷新错误信号，连续失败时触发
    
    Attributes:
        refresh_interval: 刷新间隔（秒）
        current_user_stocks: 当前用户自选股列表
    """
    
    # 定义信号
    data_updated = QtCore.pyqtSignal(list, bool)  # 数据列表, 是否全部失败
    refresh_error = QtCore.pyqtSignal()
    
    def __init__(self):
        """初始化刷新工作线程"""
        super().__init__()
        self._is_running = False
        self.refresh_interval = 5
        self.current_user_stocks: List[str] = []
        self._lock = QtCore.QMutex()  # 使用Qt互斥锁
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._processor = StockCodeProcessor()
        # self._data_change_detector = DataChangeDetector() # 使用StockManager的检测器
        self._last_successful_update = 0
        
    def start_refresh(self, user_stocks: List[str], refresh_interval: int):
        """
        启动刷新
        
        Args:
            user_stocks: 用户股票列表
            refresh_interval: 刷新间隔（秒）
        """
        self._lock.lock()
        self.current_user_stocks = user_stocks
        self.refresh_interval = refresh_interval
        self._lock.unlock()
        
        if not self.isRunning():
            self._is_running = True
            self.start()
        
        app_logger.info("后台刷新线程已启动")
        app_logger.debug(f"刷新间隔: {self.refresh_interval}秒")
        
    def stop_refresh(self):
        """停止刷新线程"""
        self._is_running = False
        self.wait(2000)  # 等待线程结束
        app_logger.info("后台刷新线程已停止")
        
    def update_stocks(self, user_stocks: List[str]):
        """更新用户股票列表"""
        self._lock.lock()
        self.current_user_stocks = user_stocks
        self._lock.unlock()
        app_logger.info(f"刷新线程股票列表已更新: {user_stocks}")
        
    def update_interval(self, refresh_interval: int):
        """更新刷新间隔"""
        self._lock.lock()
        self.refresh_interval = refresh_interval
        self._lock.unlock()
        app_logger.info(f"刷新线程间隔已更新: {refresh_interval}")
        
    def run(self):
        """线程执行入口"""
        # 减少启动延迟，给系统网络连接一些初始化时间
        app_logger.info("后台刷新线程启动，等待1秒初始化网络连接...")
        self.msleep(1000)
        
        if not self._is_running:
            return
            
        self._lock.lock()
        local_user_stocks = self.current_user_stocks[:]
        local_refresh_interval = self.refresh_interval
        self._lock.unlock()
        
        while self._is_running:
            try:
                # 检查是否有配置更新
                self._lock.lock()
                if (local_user_stocks != self.current_user_stocks or 
                    local_refresh_interval != self.refresh_interval):
                    local_user_stocks = self.current_user_stocks[:]
                    local_refresh_interval = self.refresh_interval
                    app_logger.info(f"刷新线程检测到配置变更，更新本地缓存: 股票={local_user_stocks}, 间隔={local_refresh_interval}")
                self._lock.unlock()
                
                # 检查是否需要等待下次刷新（无股票时）
                if not local_user_stocks:
                    sleep_time = local_refresh_interval if is_market_open() else 60
                    # 分段睡眠以便能及时响应停止信号
                    for _ in range(int(sleep_time)):
                        if not self._is_running:
                            break
                        self.sleep(1)
                    if not self._is_running:
                        break
                    continue

                # 获取数据
                app_logger.debug(f"需要获取 {len(local_user_stocks)} 只股票数据")
                
                # 使用 stock_manager 获取和处理数据
                from stock_monitor.core.stock_manager import stock_manager
                stocks, failed_count = stock_manager.fetch_and_process_stocks(local_user_stocks)
                
                # 检查变化并更新
                force_update = not hasattr(self, '_initial_update_done')
                # 使用 stock_manager 进行变更检测
                if force_update or stock_manager.has_stock_data_changed(stocks):
                    stock_manager.update_last_stock_data(stocks)
                    if not hasattr(self, '_initial_update_done'):
                        self._initial_update_done = True
                    
                    # 发送信号
                    self.data_updated.emit(stocks, failed_count == len(local_user_stocks) and len(local_user_stocks) > 0)
                    self._last_successful_update = time.time()
                
                self._consecutive_failures = 0
                
                # 休眠
                sleep_time = local_refresh_interval if is_market_open() else 60
                if sleep_time < 1:
                    sleep_time = 1
                    
                # 同样分段休眠
                for _ in range(int(sleep_time)):
                    if not self._is_running:
                        break
                    self.sleep(1)
                # 处理剩余的小数秒
                if self._is_running and (sleep_time % 1 > 0):
                    self.msleep(int((sleep_time % 1) * 1000))

            except Exception as e:
                app_logger.error(f'行情刷新异常: {e}')
                self._consecutive_failures += 1
                
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self.refresh_error.emit()
                    self._consecutive_failures = 0
                
                self.sleep(5)