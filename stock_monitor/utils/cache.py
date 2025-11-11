"""
缓存管理模块
用于缓存股票数据，减少网络请求频率

该模块提供了基于LRU（最近最少使用）策略的数据缓存功能，
可以有效减少对网络API的请求次数，提高应用性能。
"""

import time
from typing import Dict, Any, Optional
from collections import OrderedDict
from .logger import app_logger

def is_market_open():
    """检查A股是否开市"""
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))

class DataCache:
    """数据缓存管理器，支持LRU淘汰策略"""
    
    def __init__(self, default_ttl: int = 30, max_size: int = 1000):
        """
        初始化缓存管理器
        
        Args:
            default_ttl (int): 默认缓存过期时间（秒），默认30秒
            max_size (int): 缓存最大容量（项数），默认1000项
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        app_logger.debug("数据缓存管理器初始化完成")
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存数据
        
        如果缓存已满，会根据LRU策略自动淘汰最久未使用的项。
        
        Args:
            key (str): 缓存键
            data (Any): 要缓存的数据
            ttl (Optional[int]): 过期时间（秒），如果为None则使用默认值
        """
        # 不再验证股票数据完整性，因为实时行情数据不应该被缓存
        # 保留此函数以供其他非实时数据使用
        
        if ttl is None:
            ttl = self.default_ttl
            
        # 如果缓存已满，删除最久未使用的项
        if len(self._cache) >= self.max_size:
            # 删除最久未使用的项（OrderedDict的第一个元素）
            oldest_key, _ = self._cache.popitem(last=False)
            app_logger.debug(f"LRU淘汰: 删除最久未使用的缓存项 {oldest_key}")
            
        self._cache[key] = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
        # 将该项移到最后（表示最近使用）
        self._cache.move_to_end(key)
        app_logger.debug(f"设置缓存: {key}, TTL: {ttl}秒")
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存数据
        
        如果缓存项存在且未过期，则返回缓存数据并更新其访问时间；
        如果缓存项不存在或已过期，则返回None并删除过期项。
        
        Args:
            key (str): 缓存键
            
        Returns:
            Optional[Any]: 缓存数据，如果不存在或已过期则返回None
        """
        # 对于实时行情数据，不使用缓存
        # 保留此函数以供其他非实时数据使用
        
        if key not in self._cache:
            app_logger.debug(f"缓存未命中: {key}")
            return None
            
        cache_entry = self._cache[key]
        elapsed = time.time() - cache_entry['timestamp']
        
        if elapsed > cache_entry['ttl']:
            # 缓存已过期，删除并返回None
            del self._cache[key]
            app_logger.debug(f"缓存已过期并删除: {key}")
            return None
            
        # 将访问的项移到最后（表示最近使用）
        self._cache.move_to_end(key)
        app_logger.debug(f"缓存命中: {key}, 剩余时间: {cache_entry['ttl'] - elapsed:.1f}秒")
        return cache_entry['data']
    
    def get_with_market_aware_ttl(self, key: str) -> Optional[Any]:
        """
        获取缓存数据，根据市场状态使用不同的TTL
        
        开市期间使用较短的TTL，闭市期间使用较长的TTL
        
        Args:
            key (str): 缓存键
            
        Returns:
            Optional[Any]: 缓存数据，如果不存在或已过期则返回None
        """
        if key not in self._cache:
            app_logger.debug(f"缓存未命中: {key}")
            return None
            
        cache_entry = self._cache[key]
        # 根据市场状态确定实际的TTL
        actual_ttl = cache_entry['ttl']
        if not is_market_open():
            # 闭市期间，将TTL延长到10倍（但不超过1小时）
            actual_ttl = min(cache_entry['ttl'] * 10, 3600)
            
        elapsed = time.time() - cache_entry['timestamp']
        
        if elapsed > actual_ttl:
            # 缓存已过期，删除并返回None
            del self._cache[key]
            app_logger.debug(f"缓存已过期并删除: {key}")
            return None
            
        # 将访问的项移到最后（表示最近使用）
        self._cache.move_to_end(key)
        app_logger.debug(f"缓存命中: {key}, 剩余时间: {actual_ttl - elapsed:.1f}秒")
        return cache_entry['data']
    
    def clear(self, key: Optional[str] = None) -> None:
        """
        清除缓存
        
        Args:
            key (Optional[str]): 缓存键，如果为None则清除所有缓存
        """
        if key is None:
            self._cache.clear()
            app_logger.debug("已清除所有缓存")
        else:
            if key in self._cache:
                del self._cache[key]
                app_logger.debug(f"已清除缓存: {key}")
    
    def cleanup_expired(self) -> int:
        """
        清理过期缓存
        
        遍历所有缓存项，删除已过期的项。
        
        Returns:
            int: 清理的缓存项数量
        """
        current_time = time.time()
        expired_keys = []
        
        for key, cache_entry in self._cache.items():
            # 根据市场状态确定实际的TTL
            actual_ttl = cache_entry['ttl']
            if not is_market_open():
                # 闭市期间，将TTL延长到10倍（但不超过1小时）
                actual_ttl = min(cache_entry['ttl'] * 10, 3600)
                
            if current_time - cache_entry['timestamp'] > actual_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            
        app_logger.debug(f"清理了 {len(expired_keys)} 个过期缓存项")
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        返回当前缓存的状态信息，包括总项数、过期项数、有效项数等。
        
        Returns:
            Dict[str, Any]: 包含缓存统计信息的字典
        """
        total_items = len(self._cache)
        current_time = time.time()
        
        expired_count = 0
        for cache_entry in self._cache.values():
            # 根据市场状态确定实际的TTL
            actual_ttl = cache_entry['ttl']
            if not is_market_open():
                # 闭市期间，将TTL延长到10倍（但不超过1小时）
                actual_ttl = min(cache_entry['ttl'] * 10, 3600)
                
            if current_time - cache_entry['timestamp'] > actual_ttl:
                expired_count += 1
                
        return {
            'total_items': total_items,
            'expired_items': expired_count,
            'valid_items': total_items - expired_count,
            'max_size': self.max_size,
            'usage_percentage': (total_items / self.max_size) * 100 if self.max_size > 0 else 0
        }


# 创建全局缓存实例
global_cache = DataCache()






