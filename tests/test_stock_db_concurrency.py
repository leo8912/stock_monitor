#!/usr/bin/env python
"""StockDatabase 并发读写回归测试。

覆盖 T02 修复目标：
- 连接归属线程本地化，杜绝跨线程复用同一 Connection
- 全局写锁串行化写事务，读路径互不阻塞
- 并发结束后数据库完整性良好（PRAGMA integrity_check == ok）
"""

import os
import sqlite3
import threading
import unittest
from unittest.mock import patch

from stock_monitor.data.stock.stock_db import StockDatabase, get_db_pool


def _safe_remove(path: str) -> None:
    """清理测试产生的临时文件，忽略删除失败（句柄未释放等）。"""
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
    except OSError:
        # 测试清理路径：删除失败不影响断言结果
        pass


class TestStockDatabaseConcurrency(unittest.TestCase):
    """多线程混合读写场景测试。"""

    THREADS = 8
    ITERATIONS = 100

    def setUp(self):
        self.test_db_path = f"test_stocks_{self._testMethodName}.db"
        for suffix in ("", "-wal", "-shm"):
            _safe_remove(self.test_db_path + suffix)

        self.patcher_config = patch(
            "stock_monitor.data.stock.stock_db.get_config_dir", return_value="."
        )
        self.patcher_config.start()

        self.patcher_db_file = patch(
            "stock_monitor.data.stock.stock_db.DB_FILE", self.test_db_path
        )
        self.patcher_db_file.start()

        # 跳过基础数据导入，避免向测试库灌入数千条记录
        self.patcher_is_empty = patch(
            "stock_monitor.data.stock.stock_db.StockDatabase.is_empty",
            return_value=False,
        )
        self.patcher_is_empty.start()

        StockDatabase._instance = None
        self.db = StockDatabase()

        # 关闭初始化阶段主线程持有的连接，使后续并发连接数只由工作线程产生
        get_db_pool().close_all()

    def tearDown(self):
        get_db_pool().close_all()
        self.patcher_config.stop()
        self.patcher_db_file.stop()
        self.patcher_is_empty.stop()
        StockDatabase._instance = None
        for suffix in ("", "-wal", "-shm"):
            _safe_remove(self.test_db_path + suffix)

    def test_concurrent_mixed_read_write(self):
        """8 线程各 100 次混合写入+读取，验证无锁错且数据完整。"""
        errors: list[Exception] = []
        errors_lock = threading.Lock()
        barrier = threading.Barrier(self.THREADS)

        def worker(worker_id: int) -> None:
            try:
                barrier.wait(timeout=10)
                for i in range(self.ITERATIONS):
                    code = f"sh{worker_id:02d}{i:04d}"
                    self.db.insert_stocks(
                        [
                            {
                                "code": code,
                                "name": f"name{worker_id}_{i}",
                                "pinyin": "pinyin",
                                "abbr": "abbr",
                            }
                        ]
                    )
                    # 混合读取，触发线程本地连接的复用路径
                    self.db.search_stocks(f"name{worker_id}")
            except Exception as exc:  # noqa: BLE001 - 收集所有线程异常后统一断言
                with errors_lock:
                    errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(tid,)) for tid in range(self.THREADS)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)

        # 1. 无任何线程异常（重点：无 ProgrammingError / database is locked）
        for exc in errors:
            self.assertNotIsInstance(
                exc, sqlite3.ProgrammingError, msg=f"出现 ProgrammingError: {exc!r}"
            )
            self.assertNotIn("database is locked", str(exc))
        self.assertEqual(errors, [], msg=f"并发读写出现异常: {errors!r}")

        # 2. 连接池登记的连接数不超过线程数（每线程至多一个连接）
        stats = get_db_pool().get_stats()
        self.assertLessEqual(stats["total_cached"], self.THREADS, msg=str(stats))
        self.assertLessEqual(stats["active_pools"], self.THREADS, msg=str(stats))

        # 3. 写入总数正确（每条记录 code 唯一）
        # 注意：sqlite3.Connection 的 `with` 不关闭连接，需显式 close 以免占用句柄
        conn = sqlite3.connect(self.test_db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(total, self.THREADS * self.ITERATIONS)

        # 4. 并发结束后数据库完整性良好
        conn = sqlite3.connect(self.test_db_path)
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(integrity, "ok")


if __name__ == "__main__":
    unittest.main()
