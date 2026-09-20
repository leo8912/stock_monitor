"""
统一缓存管理模块
提供 L1（内存 LRU）/ L2（SQLite）两级缓存抽象
"""

import contextlib
import re
import sqlite3
import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

from stock_monitor.utils.logger import app_logger

# 表名白名单校验：只允许常规 SQL 标识符，防 SQL 注入（S608）
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_table_name(table_name: str) -> str:
    """校验 SQLite 表名合法性，非法时抛 ValueError。

    表名无法通过参数占位符绑定，只能拼接进 SQL，因此必须做白名单校验。
    """
    if not isinstance(table_name, str) or not _TABLE_NAME_RE.match(table_name):
        raise ValueError(f"非法的缓存表名: {table_name!r}")
    return table_name


class LRUCache:
    """线程安全的 LRU 内存缓存（L1）"""

    def __init__(self, max_size: int = 256, default_ttl: float = 300.0) -> None:
        """初始化 L1 内存 LRU 缓存。

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

    def get(self, key: str, ttl_override: float = None) -> Optional[Any]:
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

    # 兼容量化引擎历史 API；新代码优先使用 stats 属性。
    def get_stats(self) -> dict:
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


class SQLiteCache:
    """SQLite 持久化缓存（L2）"""

    def __init__(self, db_path: str, table_name: str = "cache") -> None:
        """初始化 L2 SQLite 持久化缓存并按需建表。

        Args:
            db_path: SQLite 数据库文件路径。
            table_name: 缓存表名（会做标识符白名单校验）。
        """
        self._db_path = db_path
        self._table_name = _validate_table_name(table_name)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """确保数据库目录与缓存表存在。"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
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
        """创建并返回一个新的 SQLite 连接。"""
        return sqlite3.connect(self._db_path, timeout=5)

    @contextlib.contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """借用连接的上下文管理器，退出时确保 conn.close()。

        注意：sqlite3.Connection 自带的 `with conn:` 只负责事务提交/回滚，
        **不会关闭连接**，直接使用会泄漏句柄（G-4）。此处显式关闭。
        """
        conn = self._get_conn()
        try:
            yield conn
        finally:
            conn.close()

    def get(self, key: str) -> Optional[str]:
        """从 SQLite 读取未过期值；过期或异常返回 None。"""
        with self._lock:
            try:
                with self._connection() as conn:
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
        """写入/更新 SQLite 中的键值（写入时计算过期时间戳）。"""
        with self._lock:
            try:
                now = time.time()
                with self._connection() as conn:
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
        """删除 SQLite 中的键；删除到行返回 True，否则 False。"""
        with self._lock:
            try:
                with self._connection() as conn:
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
        """清空 SQLite 缓存表。"""
        with self._lock:
            try:
                with self._connection() as conn:
                    conn.execute(f"DELETE FROM {self._table_name}")
                    conn.commit()
            except Exception as e:
                app_logger.debug(f"SQLite缓存清空失败: {e}")

    def cleanup_expired(self) -> int:
        """清理过期条目，返回删除数量"""
        with self._lock:
            try:
                with self._connection() as conn:
                    cursor = conn.execute(
                        f"DELETE FROM {self._table_name} WHERE expiry < ?",
                        (time.time(),),
                    )
                    conn.commit()
                    return cursor.rowcount
            except Exception as e:
                app_logger.warning(f"SQLite缓存清理过期条目失败: {e}", exc_info=True)
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
    ) -> None:
        """初始化两级缓存（L1 内存 + 可选 L2 SQLite）。

        Args:
            l1_max_size: L1 最大条目数。
            l1_ttl: L1 默认过期秒数。
            l2_db_path: L2 数据库路径；为 None 时禁用 L2。
            l2_ttl: L2 默认过期秒数。
            cache_name: L2 表名后缀（cache_<name>）。
        """
        self._l1 = LRUCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self._l2 = None
        if l2_db_path:
            self._l2 = SQLiteCache(l2_db_path, table_name=f"cache_{cache_name}")
        self._l2_ttl = l2_ttl
        self._name = cache_name

    def get(self, key: str) -> Optional[Any]:
        """按 L1 → L2 顺序查找，L2 命中时回填 L1。"""
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
        """同时写入 L1 与 L2（L2 值以 JSON 序列化）。"""
        self._l1.set(key, value, ttl=l1_ttl)
        if self._l2:
            import json

            try:
                raw = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                raw = str(value)
            self._l2.set(key, raw, ttl=l2_ttl or self._l2_ttl)

    def delete(self, key: str) -> None:
        """从 L1 与 L2 中删除键。"""
        self._l1.delete(key)
        if self._l2:
            self._l2.delete(key)

    def clear(self) -> None:
        """清空 L1 与 L2。"""
        self._l1.clear()
        if self._l2:
            self._l2.clear()

    @property
    def stats(self) -> dict:
        """返回两级缓存统计信息（L1 明细 + 是否启用 L2）。"""
        result = {"l1": self._l1.stats, "l2_enabled": self._l2 is not None}
        if self._l2:
            result["l2"] = {"db_path": self._l2._db_path}
        return result
