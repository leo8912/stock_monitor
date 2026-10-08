"""
统一缓存管理模块
提供线程安全的 LRU 内存缓存（量化引擎等共享）
"""

import threading
import time
from collections import OrderedDict
from typing import Any


class LRUCache:
    """线程安全的 LRU 内存缓存"""

    def __init__(self, max_size: int = 256, default_ttl: float = 300.0) -> None:
        """初始化 LRU 缓存。

        Args:
            max_size: 最大条目数，超出时淘汰最久未使用项。
            default_ttl: 默认过期时间（秒）。
        """
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, ttl_override: float = None) -> Any | None:
        """读取键值；命中且未过期返回值并刷新 LRU 次序，否则返回 None。"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if ttl_override is not None:
                    expiry = expiry - self._default_ttl + ttl_override
                if expiry > time.time():
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(
        self, key: str, value: Any, ttl: float = None, ttl_override: float = None
    ) -> None:
        """写入/更新键值，可选自定义 ttl；超容量时淘汰最久未使用项。"""
        with self._lock:
            if ttl is None:
                ttl = ttl_override if ttl_override is not None else self._default_ttl
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> bool:
        """删除键；存在并成功删除返回 True，否则 False。"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存并重置命中/未命中计数。"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        """返回缓存统计（当前大小、最大容量、命中率等）。"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }

    def get_stats(self) -> dict:
        """兼容量化引擎历史 API；新代码优先使用 stats 属性。"""
        stats = self.stats
        return {
            **stats,
            "hit_rate": f"{stats['hit_rate'] * 100:.1f}%",
            "avg_ttl": self._default_ttl,
        }

    @property
    def cache(self):
        """兼容量化诊断代码的缓存视图。"""
        return self._cache

    @property
    def max_size(self) -> int:
        return self._max_size

    @property
    def default_ttl(self) -> float:
        return self._default_ttl
