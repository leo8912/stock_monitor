"""
股票数据缓存模块
用于缓存股票基础数据，避免重复加载和处理
"""

import time
from typing import List, Dict, Optional
from .logger import app_logger


class StockDataCache:
    """股票数据缓存管理器"""
    
    def __init__(self):
        self._cache: Optional[List[Dict[str, str]]] = None
        self._cache_time: float = 0
        self._cache_ttl: int = 300  # 5分钟缓存时间
        
    def get_stock_data(self) -> List[Dict[str, str]]:
        """
        获取股票数据，带缓存机制
        
        Returns:
            List[Dict[str, str]]: 股票数据列表
        """
        current_time = time.time()
        
        # 检查缓存是否有效
        if self._cache is not None and (current_time - self._cache_time) < self._cache_ttl:
            app_logger.debug("使用缓存的股票数据")
            return self._cache
            
        # 加载新的股票数据
        try:
            stock_data = self._load_stock_data_from_db()
            self._cache = stock_data
            self._cache_time = current_time
            app_logger.debug("重新加载股票数据并更新缓存")
            return stock_data
        except Exception as e:
            app_logger.error(f"加载股票数据失败: {e}")
            # 如果有缓存，即使过期也返回缓存数据
            if self._cache is not None:
                app_logger.warning("返回过期的缓存数据")
                return self._cache
            # 否则返回空列表
            return []
            
    def _load_stock_data_from_db(self) -> List[Dict[str, str]]:
        """
        从数据库加载股票数据
        
        Returns:
            List[Dict[str, str]]: 股票数据列表
            
        Raises:
            Exception: 数据库访问失败时抛出异常
        """
        try:
            from stock_monitor.data.stock.stock_db import stock_db
            stocks = stock_db.get_all_stocks()
            app_logger.debug(f"从数据库加载股票数据成功，共 {len(stocks)} 条记录")
            return stocks
        except Exception as e:
            app_logger.warning(f"无法从数据库加载股票数据: {e}")
            # 抛出异常让调用者处理
            raise e

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache = None
        self._cache_time = 0
        app_logger.debug("股票数据缓存已清除")


# 创建全局股票数据缓存实例
global_stock_cache = StockDataCache()