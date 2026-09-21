"""Tests for cache manager (L1/L2)"""

import os
import tempfile
from unittest.mock import patch

import pytest

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
        # Mock time so that set uses t=1000 (expiry=1060) and get uses t=2000 (past expiry)
        counter = [0]

        def fake_time():
            counter[0] += 1
            if counter[0] == 1:
                return 1000.0  # during set (expiry = 1000 + 60 = 1060)
            return 2000.0  # during get (2000 > 1060 → expired)

        with patch("stock_monitor.core.cache_manager.time.time", side_effect=fake_time):
            cache.set("key", "value", ttl=60)
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
        cache.set("long", "val", ttl=3600)
        # Directly insert an entry with expiry in the past
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO {cache._table_name} (key, value, expiry, created_at) VALUES (?, ?, ?, ?)",
                ("short", "val", 1.0, 1.0),
            )
            conn.commit()
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


class TestSQLiteCacheRobustness:
    """G-4 / G-5 回归测试：连接句柄关闭 + 表名白名单校验"""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "robust.db")

    def test_connections_are_closed_after_operations(self, monkeypatch):
        """G-4: 每次操作后 SQLite 连接必须关闭，不得泄漏句柄"""
        from stock_monitor.core import cache_manager

        opened = []
        real_connect = cache_manager.sqlite3.connect

        class _TrackedConn:
            def __init__(self, conn):
                self._conn = conn
                self.closed = False

            def __getattr__(self, name):
                return getattr(self._conn, name)

            def close(self):
                self.closed = True
                self._conn.close()

        def _factory(*args, **kwargs):
            tracked = _TrackedConn(real_connect(*args, **kwargs))
            opened.append(tracked)
            return tracked

        monkeypatch.setattr(cache_manager.sqlite3, "connect", _factory)

        cache = SQLiteCache(self.db_path)
        cache.set("key", "value", ttl=60)
        assert cache.get("key") == "value"
        cache.delete("key")

        assert opened, "应至少建立过一次连接"
        assert all(c.closed for c in opened), "所有 SQLite 连接必须被关闭 (G-4)"

    def test_invalid_table_name_rejected(self):
        """G-5: 含 SQL 元字符的非法表名必须被拒绝（防注入）"""
        with pytest.raises(ValueError):
            SQLiteCache(self.db_path, table_name="bad; DROP TABLE x")

    def test_valid_table_name_accepted(self):
        """G-5: 合法标识符表名正常通过"""
        cache = SQLiteCache(self.db_path, table_name="cache_demo_1")
        cache.set("k", "v", ttl=60)
        assert cache.get("k") == "v"
