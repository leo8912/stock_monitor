"""量化引擎使用的共享缓存入口。"""

from __future__ import annotations

import threading

from stock_monitor.core.cache_manager import LRUCache

_bars_cache_instance: LRUCache | None = None
_init_lock = threading.Lock()


def get_bars_cache(max_size=128, ttl=60) -> LRUCache:
    """获取惰性初始化的全局 K 线缓存。

    max_size/ttl 仅在首次调用（创建实例）时生效，后续调用忽略。
    """
    global _bars_cache_instance
    if _bars_cache_instance is None:
        with _init_lock:
            if _bars_cache_instance is None:
                _bars_cache_instance = LRUCache(max_size, ttl)
    return _bars_cache_instance
