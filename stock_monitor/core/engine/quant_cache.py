"""量化引擎使用的共享缓存入口。"""

from __future__ import annotations

from stock_monitor.core.cache_manager import LRUCache


class LRUCacheWithTTL(LRUCache):
    """兼容量化历史 API 的缓存别名。"""

    def __init__(self, max_size=128, default_ttl=60) -> None:
        super().__init__(max_size=max_size, default_ttl=default_ttl)


_bars_cache_instance: LRUCacheWithTTL | None = None


def get_bars_cache(max_size=128, ttl=60) -> LRUCacheWithTTL:
    """获取惰性初始化的全局 K 线缓存。"""
    global _bars_cache_instance
    if _bars_cache_instance is None:
        _bars_cache_instance = LRUCacheWithTTL(max_size, ttl)
    return _bars_cache_instance
