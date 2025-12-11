"""
数据变化检测模块
用于检测股票数据是否发生变化
"""

from typing import List, Tuple, Dict
from ..utils.logger import app_logger


class DataChangeDetector:
    """数据变化检测器"""
    
    def __init__(self):
        """初始化数据变化检测器"""
        self._last_stock_data: Dict[str, str] = {}
    
    def has_stock_data_changed(self, stocks: List[Tuple]) -> bool:
        """
        检查股票数据是否发生变化
        
        Args:
            stocks: 当前股票数据列表
            
        Returns:
            bool: 数据是否发生变化
        """
        # 如果没有缓存数据，认为发生了变化
        if not self._last_stock_data:
            return True
            
        # 比较每只股票的数据
        for stock in stocks:
            name, price, change, color, seal_vol, seal_type = stock
            key = f"{name}_{price}_{change}_{color}_{seal_vol}_{seal_type}"
            
            # 如果这只股票之前没有数据，认为发生了变化
            if name not in self._last_stock_data:
                return True
                
            # 如果数据不匹配，认为发生了变化
            if self._last_stock_data[name] != key:
                return True
                
        # 检查是否有股票被移除
        current_names = [stock[0] for stock in stocks]
        for name in self._last_stock_data.keys():
            if name not in current_names:
                return True
                
        # 数据没有变化
        return False
    
    def update_last_stock_data(self, stocks: List[Tuple]) -> None:
        """
        更新最后股票数据缓存
        
        Args:
            stocks: 当前股票数据列表
        """
        self._last_stock_data.clear()
        for stock in stocks:
            name, price, change, color, seal_vol, seal_type = stock
            key = f"{name}_{price}_{change}_{color}_{seal_vol}_{seal_type}"
            self._last_stock_data[name] = key
            
        app_logger.debug(f"更新股票数据缓存，共{len(self._last_stock_data)}只股票")