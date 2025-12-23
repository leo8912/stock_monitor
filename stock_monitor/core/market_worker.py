from PyQt6 import QtCore
import time
from typing import Dict, Any
from stock_monitor.utils.logger import app_logger
from stock_monitor.config.manager import is_market_open
from stock_monitor.config.manager import is_market_open

class MarketStatsWorker(QtCore.QThread):
    """全市场统计工作线程"""
    
    # 信号：上涨数, 下跌数, 平盘数, 总数
    stats_updated = QtCore.pyqtSignal(int, int, int, int)
    
    def __init__(self):
        super().__init__()
        self._is_running = False
        self.interval = 60  # 默认60秒刷新一次
        
    def start_worker(self):
        """启动工作线程"""
        if not self.isRunning():
            self._is_running = True
            self.start()
            app_logger.info("市场统计后台线程已启动")
            
    def stop_worker(self):
        """停止工作线程"""
        self._is_running = False
        self.wait(2000)
        app_logger.info("市场统计后台线程已停止")
        
    def run(self):
        """线程执行入口"""
        # 初始延迟
        self.msleep(2000)
        
        while self._is_running:
            try:
                # 检查市场是否开市，闭市期间延长刷新间隔
                if not is_market_open():
                     # 闭市期间每5分钟检查一次，或者直接sleep
                     # 为了响应停止信号，使用循环sleep
                     for _ in range(60): 
                         if not self._is_running: return
                         self.sleep(5)
                     continue

                app_logger.debug("开始获取全市场数据...")
                from stock_monitor.core.stock_manager import stock_manager
                market_data = stock_manager.get_all_market_data()
                
                if market_data:
                    stats = self._calculate_stats(market_data)
                    self.stats_updated.emit(
                        stats['up_count'], 
                        stats['down_count'], 
                        stats['flat_count'], 
                        stats['total_count']
                    )
                    app_logger.debug(f"市场统计更新: {stats}")
                else:
                    app_logger.warning("获取全市场数据失败")
                
                # 休眠
                for _ in range(self.interval):
                    if not self._is_running:
                        break
                    self.sleep(1)
                    
            except Exception as e:
                app_logger.error(f"市场统计线程异常: {e}")
                self.sleep(10)

    def _calculate_stats(self, data: Dict[str, Any]) -> Dict[str, int]:
        """计算市场统计数据"""
        up = 0
        down = 0
        flat = 0
        total = 0
        
        for code, info in data.items():
            if not isinstance(info, dict):
                continue
                
            name = info.get('name', '')
            # 跳过指数
            if '指数' in name or 'Ａ股' in name:
                continue
                
            try:
                close = float(info.get('close', 0))
                now = float(info.get('now', 0))
                
                if close == 0:
                    flat += 1
                elif now > close:
                    up += 1
                elif now < close:
                    down += 1
                else:
                    flat += 1
                    
                total += 1
            except (ValueError, TypeError):
                continue
                
        return {
            'up_count': up,
            'down_count': down,
            'flat_count': flat,
            'total_count': total
        }
