"""
统一缓存管理模块
提供 L1（内存 LRU）/ L2（SQLite）两级缓存抽象
"""

import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

from stock_monitor.utils.logger import app_logger


class LRUCache:
    """线程安全的 LRU 内存缓存（L1）"""

    def __init__(self, max_size: int = 256, default_ttl: float = 300.0):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if expiry > time.time():
                    self._cache.move_to_end(key)
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any, ttl: float = None) -> None:
        with self._lock:
            if ttl is None:
                ttl = self._default_ttl
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.time() + ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


class SQLiteCache:
    """SQLite 持久化缓存（L2）"""

    def __init__(self, db_path: str, table_name: str = "cache"):
        self._db_path = db_path
        self._table_name = table_name
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._get_conn() as conn:
            conn.execute(
                f"""CREATE TABLE IF NOT EXISTS {self._table_name} (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expiry REAL NOT NULL,
                    created_at REAL NOT NULL
                )"""
            )
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            try:
                with self._get_conn() as conn:
                    row = conn.execute(
                        f"SELECT value, expiry FROM {self._table_name} WHERE key = ?",
                        (key,),
                    ).fetchone()
                    if row and row[1] > time.time():
                        return row[0]
                    elif row:
                        conn.execute(
                            f"DELETE FROM {self._table_name} WHERE key = ?",
                            (key,),
                        )
                        conn.commit()
            except Exception as e:
                app_logger.debug(f"SQLite缓存读取失败 [{key}]: {e}")
        return None

    def set(self, key: str, value: str, ttl: float = 3600.0) -> None:
        with self._lock:
            try:
                now = time.time()
                with self._get_conn() as conn:
                    conn.execute(
                        f"""INSERT OR REPLACE INTO {self._table_name}
                            (key, value, expiry, created_at)
                            VALUES (?, ?, ?, ?)""",
                        (key, value, now + ttl, now),
                    )
                    conn.commit()
            except Exception as e:
                app_logger.debug(f"SQLite缓存写入失败 [{key}]: {e}")

    def delete(self, key: str) -> bool:
        with self._lock:
            try:
                with self._get_conn() as conn:
                    cursor = conn.execute(
                        f"DELETE FROM {self._table_name} WHERE key = ?",
                        (key,),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as e:
                app_logger.debug(f"SQLite缓存删除失败 [{key}]: {e}")
        return False

    def clear(self) -> None:
        with self._lock:
            try:
                with self._get_conn() as conn:
                    conn.execute(f"DELETE FROM {self._table_name}")
                    conn.commit()
            except Exception as e:
                app_logger.debug(f"SQLite缓存清空失败: {e}")

    def cleanup_expired(self) -> int:
        """清理过期条目，返回删除数量"""
        with self._lock:
            try:
                with self._get_conn() as conn:
                    cursor = conn.execute(
                        f"DELETE FROM {self._table_name} WHERE expiry < ?",
                        (time.time(),),
                    )
                    conn.commit()
                    return cursor.rowcount
            except Exception:
                pass
        return 0


class TwoLevelCache:
    """
    两级缓存：L1（内存）→ L2（SQLite）

    读取顺序：L1 → L2 → None
    写入策略：同时写入 L1 和 L2
    """

    def __init__(
        self,
        l1_max_size: int = 256,
        l1_ttl: float = 300.0,
        l2_db_path: str = None,
        l2_ttl: float = 3600.0,
        cache_name: str = "default",
    ):
        self._l1 = LRUCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self._l2 = None
        if l2_db_path:
            self._l2 = SQLiteCache(l2_db_path, table_name=f"cache_{cache_name}")
        self._l2_ttl = l2_ttl
        self._name = cache_name

    def get(self, key: str) -> Optional[Any]:
        # L1 查找
        value = self._l1.get(key)
        if value is not None:
            return value

        # L2 查找
        if self._l2:
            raw = self._l2.get(key)
            if raw is not None:
                import json

                try:
                    value = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    value = raw
                # 回填 L1
                self._l1.set(key, value)
                return value

        return None

    def set(
        self, key: str, value: Any, l1_ttl: float = None, l2_ttl: float = None
    ) -> None:
        self._l1.set(key, value, ttl=l1_ttl)
        if self._l2:
            import json

            try:
                raw = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                raw = str(value)
            self._l2.set(key, raw, ttl=l2_ttl or self._l2_ttl)

    def delete(self, key: str) -> None:
        self._l1.delete(key)
        if self._l2:
            self._l2.delete(key)

    def clear(self) -> None:
        self._l1.clear()
        if self._l2:
            self._l2.clear()

    @property
    def stats(self) -> dict:
        result = {"l1": self._l1.stats, "l2_enabled": self._l2 is not None}
        if self._l2:
            result["l2"] = {"db_path": self._l2._db_path}
        return result
