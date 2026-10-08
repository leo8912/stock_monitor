"""Tests for LRUCache"""

from unittest.mock import patch

from stock_monitor.core.cache_manager import LRUCache


class TestLRUCache:
    def test_set_and_get(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_missing_key_returns_none(self):
        cache = LRUCache(max_size=10)
        assert cache.get("missing") is None

    def test_expired_entry_returns_none(self):
        cache = LRUCache(max_size=10, default_ttl=1)
        counter = [0]

        def fake_time():
            counter[0] += 1
            if counter[0] == 1:
                return 1000.0  # during set (expiry = 1001)
            return 2000.0  # during get (well past expiry)

        with patch("stock_monitor.core.cache_manager.time.time", side_effect=fake_time):
            cache.set("key1", "value1")
            assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = LRUCache(max_size=10, default_ttl=60)
        counter = [0]

        def fake_time():
            counter[0] += 1
            if counter[0] <= 2:
                return 1000.0  # during set calls (keys "short" and "long")
            return 1001.0  # during get calls (past short=1000.1, before long=1060)

        with patch("stock_monitor.core.cache_manager.time.time", side_effect=fake_time):
            cache.set("short", "val", ttl=0.1)
            cache.set("long", "val", ttl=60)
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
