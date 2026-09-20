#!/usr/bin/env python
"""QA 独立验证（T02）：连接池归属模型的攻击性测试。

与工程师的 ``tests/test_stock_db_concurrency.py`` 角度不同：本文件在
``sqlite3.connect`` 层包裹 tracer，记录**每个连接的创建线程 id** 与
**每个连接实际执行 SQL 的线程 id**，从底层证明"任一连接任一时刻只被
其创建线程使用"，而不是只检查连接池自报的统计数。

另附反向验证：确认 ``_get_connection`` / ``_write_connection`` 的异常回滚
真的把未提交事务丢弃。
"""

import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from stock_monitor.data.stock import stock_db as sdb_module
from stock_monitor.data.stock.stock_db import StockDatabase, get_db_pool


class _ConnectionTracer:
    """包裹 sqlite3.connect，记录连接创建线程与实际使用线程。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.creation_thread: dict[int, int] = {}
        self.usages: list[tuple[int, int]] = []
        self._keepalive: list[sqlite3.Connection] = []
        self._real_connect = sqlite3.connect  # 在打补丁前捕获

    def connect(self, *args, **kwargs):
        conn = self._real_connect(*args, **kwargs)
        cid = id(conn)
        with self._lock:
            self.creation_thread[cid] = threading.get_ident()
            self._keepalive.append(conn)  # 保活，避免 id 被回收复用
        # trace 回调在真正执行语句的线程上被调用 → 即"使用线程"
        conn.set_trace_callback(lambda _stmt, c=cid: self._record_usage(c))
        return conn

    def _record_usage(self, cid: int) -> None:
        with self._lock:
            self.usages.append((cid, threading.get_ident()))

    def violations(self) -> list[tuple[int, int, int]]:
        """返回 (连接id, 使用线程, 创建线程)，仅含跨线程使用的违例。"""
        with self._lock:
            return [
                (cid, used, self.creation_thread.get(cid))
                for cid, used in self.usages
                if self.creation_thread.get(cid) != used
            ]

    def connections_used_by_multiple_threads(self) -> dict[int, set[int]]:
        with self._lock:
            per_conn: dict[int, set[int]] = {}
            for cid, tid in self.usages:
                per_conn.setdefault(cid, set()).add(tid)
            return {cid: tids for cid, tids in per_conn.items() if len(tids) > 1}


class TestConnectionPoolOwnership(unittest.TestCase):
    """底层归属验证：连接绝不跨线程使用。"""

    THREADS = 6
    ITERATIONS = 40  # 6 * 40 = 240 次写入 > 200

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="qa_dbpool_")
        self.db_path = os.path.join(self.tmpdir, "stocks.db")

        self._patchers = [
            patch.object(sdb_module, "get_config_dir", return_value=self.tmpdir),
            patch.object(sdb_module, "DB_FILE", "stocks.db"),
            patch.object(StockDatabase, "is_empty", return_value=False),
        ]
        for p in self._patchers:
            p.start()

        sdb_module._db_pool = None
        StockDatabase._instance = None
        self.db = StockDatabase()
        # 清掉初始化阶段主线程连接，隔离后续并发产生的连接
        get_db_pool().close_all()

    def tearDown(self) -> None:
        get_db_pool().close_all()
        for p in self._patchers:
            p.stop()
        StockDatabase._instance = None
        sdb_module._db_pool = None
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _raw_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]

    def test_no_cross_thread_connection_usage(self) -> None:
        """混合读写 + 异常回滚负载下，连接不得被非创建线程使用。"""
        tracer = _ConnectionTracer()
        errors: list[Exception] = []
        errors_lock = threading.Lock()
        barrier = threading.Barrier(self.THREADS)

        def worker(wid: int) -> None:
            try:
                barrier.wait(timeout=15)
                for i in range(self.ITERATIONS):
                    code = f"sh{wid:02d}{i:04d}"
                    self.db.insert_stocks(
                        [
                            {
                                "code": code,
                                "name": f"qa{wid}_{i}",
                                "pinyin": "pp",
                                "abbr": "aa",
                            }
                        ]
                    )
                    self.db.search_stocks(f"qa{wid}")
                    # 每 10 次触发一次读路径异常 → 走 rollback 分支
                    if i % 10 == 0:
                        try:
                            with self.db._get_connection() as conn:
                                conn.execute("SELECT * FROM __no_such_table__")
                        except sqlite3.Error:
                            pass
            except Exception as exc:  # noqa: BLE001
                with errors_lock:
                    errors.append(exc)

        with patch.object(sqlite3, "connect", tracer.connect):
            threads = [
                threading.Thread(target=worker, args=(tid,))
                for tid in range(self.THREADS)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=180)

        # 1. 无任何线程异常
        self.assertEqual(errors, [], f"并发负载出现异常: {errors!r}")

        # 2. 底层证据：无跨线程使用
        self.assertEqual(
            tracer.violations(),
            [],
            f"检测到跨线程使用连接: {tracer.violations()[:5]!r}",
        )
        multi = tracer.connections_used_by_multiple_threads()
        self.assertEqual(multi, {}, f"同一连接被多线程使用: {multi}")

        # 3. 写入总数正确
        self.assertEqual(self._raw_count(), self.THREADS * self.ITERATIONS)

        # 4. 完整性
        with sqlite3.connect(self.db_path) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


class TestRollbackOnException(unittest.TestCase):
    """反向验证：异常路径确实回滚，不污染复用连接。"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="qa_rollback_")
        self.db_path = os.path.join(self.tmpdir, "stocks.db")

        self._patchers = [
            patch.object(sdb_module, "get_config_dir", return_value=self.tmpdir),
            patch.object(sdb_module, "DB_FILE", "stocks.db"),
            patch.object(StockDatabase, "is_empty", return_value=False),
        ]
        for p in self._patchers:
            p.start()

        sdb_module._db_pool = None
        StockDatabase._instance = None
        self.db = StockDatabase()
        get_db_pool().close_all()

    def tearDown(self) -> None:
        get_db_pool().close_all()
        for p in self._patchers:
            p.stop()
        StockDatabase._instance = None
        sdb_module._db_pool = None
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _codes(self) -> set[str]:
        with sqlite3.connect(self.db_path) as conn:
            return {r[0] for r in conn.execute("SELECT code FROM stocks")}

    def test_write_connection_rolls_back_on_exception(self) -> None:
        """_write_connection 内抛异常 → 事务回滚，数据不落库。"""
        self.db.insert_stocks([{"code": "sh600010", "name": "base"}])

        with self.assertRaises(RuntimeError):
            with self.db._write_connection() as conn:
                conn.execute(
                    "INSERT INTO stocks (code,name,pinyin,abbr,market_type) "
                    "VALUES ('wrollback','y','','','A')"
                )
                raise RuntimeError("boom")

        codes = self._codes()
        self.assertIn("sh600010", codes)
        self.assertNotIn("wrollback", codes)

    def test_get_connection_rolls_back_pending_txn(self) -> None:
        """_get_connection 内抛异常 → 回滚隐式事务，后续 commit 不带走脏数据。"""
        with self.assertRaises(RuntimeError):
            with self.db._get_connection() as conn:
                conn.execute(
                    "INSERT INTO stocks (code,name,pinyin,abbr,market_type) "
                    "VALUES ('rrollback','y','','','A')"
                )
                raise RuntimeError("boom")

        # 触发一次正常写入提交；若回滚失效，脏数据会被一并提交
        self.db.insert_stocks([{"code": "sh600011", "name": "after"}])

        codes = self._codes()
        self.assertIn("sh600011", codes)
        self.assertNotIn("rrollback", codes)


if __name__ == "__main__":
    unittest.main()
