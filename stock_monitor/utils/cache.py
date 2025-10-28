"""
缓存管理模块
用于缓存股票数据，减少网络请求频率
"""

import time
from typing import Dict, Any, Optional
from .logger import app_logger


class DataCache:
    """数据缓存管理器"""
    
    def __init__(self, default_ttl: int = 30):
        """
        初始化缓存管理器
        
        Args:
            default_ttl: 默认缓存过期时间（秒）
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        app_logger.debug("数据缓存管理器初始化完成")
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存数据
        
        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 过期时间（秒），如果为None则使用默认值
        """
        if ttl is None:
            ttl = self.default_ttl
            
        self._cache[key] = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
        app_logger.debug(f"设置缓存: {key}, TTL: {ttl}秒")
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
            
        Returns:
            缓存数据，如果不存在或已过期则返回None
        """
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
            
        app_logger.debug(f"缓存命中: {key}, 剩余时间: {cache_entry['ttl'] - elapsed:.1f}秒")
        return cache_entry['data']
    
    def clear(self, key: Optional[str] = None) -> None:
        """
        清除缓存
        
        Args:
            key: 缓存键，如果为None则清除所有缓存
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
        
        Returns:
            清理的缓存项数量
        """
        current_time = time.time()
        expired_keys = []
        
        for key, cache_entry in self._cache.items():
            if current_time - cache_entry['timestamp'] > cache_entry['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
            
        app_logger.debug(f"清理了 {len(expired_keys)} 个过期缓存项")
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            包含缓存统计信息的字典
        """
        total_items = len(self._cache)
        current_time = time.time()
        
        expired_count = 0
        for cache_entry in self._cache.values():
            if current_time - cache_entry['timestamp'] > cache_entry['ttl']:
                expired_count += 1
                
        return {
            'total_items': total_items,
            'expired_items': expired_count,
            'valid_items': total_items - expired_count
        }


# 创建全局缓存实例
global_cache = DataCache()
