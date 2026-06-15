"""Tests for cache manager (L1/L2)"""

import os
import tempfile
import time

from stock_monitor.core.cache_manager import LRUCache, SQLiteCache, TwoLevelCache


class TestLRUCache:
    def test_set_and_get(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_missing_key_returns_none(self):
        cache = LRUCache(max_size=10)
        assert cache.get("missing") is None

    def test_expired_entry_returns_none(self):
        cache = LRUCache(max_size=10, default_ttl=0.01)
        cache.set("key1", "value1")
        time.sleep(0.02)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("short", "val", ttl=0.01)
        cache.set("long", "val", ttl=60)
        time.sleep(0.02)
        assert cache.get("short") is None
        assert cache.get("long") == "val"

    def test_lru_eviction(self):
        cache = LRUCache(max_size=3, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # evicts "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_lru_access_refreshes_order(self):
        cache = LRUCache(max_size=3, default_ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # refresh "a"
        cache.set("d", 4)  # evicts "b" (least recently used)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_delete(self):
        cache = LRUCache(max_size=10)
        cache.set("key", "val")
        assert cache.delete("key") is True
        assert cache.get("key") is None
        assert cache.delete("missing") is False

    def test_clear(self):
        cache = LRUCache(max_size=10)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.stats["hits"] == 0

    def test_stats(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("missing")  # miss
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1

    def test_overwrite(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("a", 1)
        cache.set("a", 2)
        assert cache.get("a") == 2


class TestSQLiteCache:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")

    def test_set_and_get(self):
        cache = SQLiteCache(self.db_path)
        cache.set("key", "value", ttl=60)
        assert cache.get("key") == "value"

    def test_missing_key(self):
        cache = SQLiteCache(self.db_path)
        assert cache.get("missing") is None

    def test_expired(self):
        cache = SQLiteCache(self.db_path)
        cache.set("key", "value", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("key") is None

    def test_delete(self):
        cache = SQLiteCache(self.db_path)
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_clear(self):
        cache = SQLiteCache(self.db_path)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert cache.get("a") is None

    def test_cleanup_expired(self):
        cache = SQLiteCache(self.db_path)
        cache.set("short", "val", ttl=0.01)
        cache.set("long", "val", ttl=60)
        time.sleep(0.02)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("long") == "val"

    def test_persistence(self):
        cache1 = SQLiteCache(self.db_path)
        cache1.set("persist", "data")
        # 新实例读取同一数据库
        cache2 = SQLiteCache(self.db_path)
        assert cache2.get("persist") == "data"


class TestTwoLevelCache:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "two_level.db")

    def test_l1_l2_fallback(self):
        cache = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=self.db_path,
            l2_ttl=60,
            cache_name="test",
        )
        cache.set("key", "value")
        # 直接从 L1 读
        assert cache.get("key") == "value"

    def test_l2_persists_across_instances(self):
        cache1 = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=self.db_path,
            l2_ttl=60,
            cache_name="persist",
        )
        cache1.set("key", {"nested": "data"})

        # 新实例，L1 为空，从 L2 恢复
        cache2 = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=self.db_path,
            l2_ttl=60,
            cache_name="persist",
        )
        assert cache2.get("key") == {"nested": "data"}

    def test_l1_only_mode(self):
        cache = TwoLevelCache(l1_max_size=10, l1_ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        assert cache.stats["l2_enabled"] is False

    def test_delete(self):
        cache = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=self.db_path,
            l2_ttl=60,
            cache_name="del",
        )
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None

    def test_clear(self):
        cache = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=self.db_path,
            l2_ttl=60,
            cache_name="clear",
        )
        cache.set("a", 1)
        cache.clear()
        assert cache.get("a") is None
