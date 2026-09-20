import os
import sqlite3
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


class TestStockDatabase(unittest.TestCase):
    def setUp(self):
        # Use a temporary database file for testing, unique per test to avoid locking issues
        self.test_db_path = f"test_stocks_{self._testMethodName}.db"
        # 预清理可能的残留文件（含 WAL/SHM），避免上一次运行的句柄干扰
        for suffix in ("", "-wal", "-shm"):
            _safe_remove(self.test_db_path + suffix)
        # Mock get_config_dir to return current directory
        self.patcher_config = patch(
            "stock_monitor.data.stock.stock_db.get_config_dir", return_value="."
        )
        self.mock_config_dir = self.patcher_config.start()

        # Mock DB_FILE constant to use our test db filename
        self.patcher_db_file = patch(
            "stock_monitor.data.stock.stock_db.DB_FILE", self.test_db_path
        )
        self.patcher_db_file.start()

        # Patch is_empty to return False, so _populate_base_data is skipped
        # This prevents auto-importing thousands of stocks into the test DB
        self.patcher_is_empty = patch(
            "stock_monitor.data.stock.stock_db.StockDatabase.is_empty",
            return_value=False,
        )
        self.mock_is_empty = self.patcher_is_empty.start()

        # Reset the singleton instance
        StockDatabase._instance = None
        self.db = StockDatabase()

        # Force Clean - ensure database is empty regardless of auto-population.
        # 注意：sqlite3.Connection 的 `with` 只提交事务、**不关闭连接**（G-4），
        # 直接使用会占用文件句柄，导致 tearDown 的 os.remove 静默失败并在仓库根
        # 残留 test_stocks_*.db。这里显式关闭。
        conn = sqlite3.connect(self.db.db_path)
        try:
            conn.execute("DELETE FROM stocks")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        # 先关闭连接池释放文件句柄，否则 Windows 下 os.remove 会静默失败并在
        # 仓库根残留 test_stocks_*.db（与 test_stock_db_concurrency.py 保持一致）。
        get_db_pool().close_all()
        self.patcher_config.stop()
        self.patcher_db_file.stop()
        self.patcher_is_empty.stop()
        StockDatabase._instance = None
        for suffix in ("", "-wal", "-shm"):
            _safe_remove(self.test_db_path + suffix)

    def test_insert_stocks_batch(self):
        """Test inserting a batch of stocks"""
        stocks = [
            {
                "code": "sh600000",
                "name": "Generic Bank",
                "pinyin": "pfyh",
                "abbr": "pfyh",
            },
            {
                "code": "sz000001",
                "name": "Generic Tech",
                "pinyin": "payh",
                "abbr": "payh",
            },
            {"code": "hk00700", "name": "Tencent", "pinyin": "txkg", "abbr": "txkg"},
        ]

        count = self.db.insert_stocks(stocks)
        self.assertEqual(count, 3)

        # Verify data
        stock1 = self.db.get_stock_by_code("sh600000")
        self.assertIsNotNone(stock1)
        self.assertEqual(stock1["name"], "Generic Bank")
        self.assertEqual(stock1["code"], "sh600000")

        stock2 = self.db.get_stock_by_code("hk00700")
        self.assertIsNotNone(stock2)
        self.assertEqual(stock2["name"], "Tencent")

    def test_connection_is_reused_within_a_thread(self):
        """同一线程的连续数据库操作应复用同一个打开的连接。"""
        with self.db._get_connection() as first_connection:
            self.assertIsNotNone(first_connection.execute("SELECT 1").fetchone())

        with self.db._get_connection() as second_connection:
            self.assertIs(first_connection, second_connection)

    def test_update_existing_stocks(self):
        """Test updating existing stocks"""
        # Initial insert
        stocks = [
            {"code": "sh600000", "name": "Old Name", "pinyin": "on", "abbr": "on"}
        ]
        self.db.insert_stocks(stocks)

        # Update
        updated_stocks = [
            {"code": "sh600000", "name": "New Name", "pinyin": "nn", "abbr": "nn"}
        ]
        count = self.db.insert_stocks(updated_stocks)
        self.assertEqual(count, 1)

        # Verify update
        stock = self.db.get_stock_by_code("sh600000")
        self.assertEqual(stock["name"], "New Name")
        self.assertEqual(stock["abbr"], "nn")

    def test_insert_mixed_new_and_existing(self):
        """Test inserting a mix of new and existing stocks"""
        # Initial insert
        self.db.insert_stocks(
            [{"code": "sh600000", "name": "Stock A", "pinyin": "a", "abbr": "a"}]
        )

        # Batch with 1 update and 1 new
        batch = [
            {
                "code": "sh600000",
                "name": "Stock A",
                "pinyin": "a",
                "abbr": "a",
            },  # Unchanged
            {"code": "sh600001", "name": "Stock B", "pinyin": "b", "abbr": "b"},  # New
        ]

        # Note: New optimized implementation returns total processed count (len(batch))
        # because tracking granular "unchanged" status is expensive in batch operations.
        count = self.db.insert_stocks(batch)

        self.assertEqual(count, 2)

        self.assertEqual(self.db.get_all_stocks_count(), 2)

    def test_insert_stocks_skips_missing_fields(self):
        """G-7: 上游缺 code/name 的记录被跳过，不触发慢速降级、不中断整批入库"""
        stocks = [
            {"code": "sh600000", "name": "Good", "pinyin": "g", "abbr": "g"},
            {"name": "NoCode"},  # 缺 code
            {"code": "sh600001"},  # 缺 name
            {"code": "sh600002", "name": "Good2", "pinyin": "g2", "abbr": "g2"},
        ]

        with patch.object(self.db, "_insert_stocks_slow") as mock_slow:
            count = self.db.insert_stocks(stocks)
            mock_slow.assert_not_called()

        self.assertEqual(count, 2)
        self.assertIsNotNone(self.db.get_stock_by_code("sh600000"))
        self.assertIsNotNone(self.db.get_stock_by_code("sh600002"))
        self.assertIsNone(self.db.get_stock_by_code("sh600001"))


if __name__ == "__main__":
    unittest.main()
