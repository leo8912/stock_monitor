#!/usr/bin/env python
"""QA 独立验证：反向/边界输入与回归防护。

覆盖 P0 修复的"预期失败/边界"路径，确认程序不崩且行为可预期：
- insert_stocks 空列表 / 缺字段 / 多余字段
- compute_market_stats 负数 / None
- SQLiteCache 表名白名单 + 连接显式关闭
- MarketDataAdapter 每线程 Session（G-10）
- QuantWorker symbols 快照隔离（G-11）
"""

import os
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch

from stock_monitor.core.cache_manager import SQLiteCache, _validate_table_name
from stock_monitor.core.data.market_data_adapter import MarketDataAdapter
from stock_monitor.core.workers.quant_worker import QuantWorker
from stock_monitor.data.stock import stock_db as sdb_module
from stock_monitor.data.stock.stock_db import StockDatabase, get_db_pool
from stock_monitor.ui.widgets.taskbar_quote_bar import TaskbarQuoteBar


class TestInsertStocksBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="qa_edge_")
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

    def test_empty_list_returns_zero(self) -> None:
        self.assertEqual(self.db.insert_stocks([]), 0)

    def test_missing_fields_are_skipped(self) -> None:
        n = self.db.insert_stocks(
            [
                {"code": "sh600000", "name": "ok"},
                {"code": "", "name": "no-code"},
                {"code": "sh600001", "name": ""},
                {"name": "no-code-field"},
            ]
        )
        self.assertEqual(n, 1)
        self.assertEqual(self.db.get_all_stocks_count(), 1)

    def test_extra_fields_ignored(self) -> None:
        n = self.db.insert_stocks(
            [{"code": "sh600002", "name": "x", "unknown": 1, "nested": {}}]
        )
        self.assertEqual(n, 1)

    def test_empty_keyword_search(self) -> None:
        self.db.insert_stocks([{"code": "sh600003", "name": "abc"}])
        self.assertIsInstance(self.db.search_stocks(""), list)


class TestComputeMarketStatsBoundary(unittest.TestCase):
    def test_negative_counts_pass_through(self) -> None:
        stats = TaskbarQuoteBar.compute_market_stats(-1, -2, -3, -6)
        self.assertEqual(stats, {"up": -1, "down": -2, "flat": -3, "total": -6})

    def test_float_coerced_to_int(self) -> None:
        self.assertEqual(
            TaskbarQuoteBar.compute_market_stats(1.9, 2.1, 3.0, 7.0)["total"], 7
        )

    def test_none_raises_type_error(self) -> None:
        """特征化：None 不是合法计数，int(None) 抛 TypeError（上游信号为 int 类型）。"""
        with self.assertRaises(TypeError):
            TaskbarQuoteBar.compute_market_stats(None, 0, 0, 0)


class TestSQLiteCacheRobustness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="qa_cache_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_table_name_whitelist(self) -> None:
        self.assertEqual(_validate_table_name("cache_1"), "cache_1")
        for bad in ("cache; DROP TABLE x", "1cache", "a-b", "", "a b"):
            with self.assertRaises(ValueError):
                _validate_table_name(bad)

    def test_invalid_table_name_rejected_at_init(self) -> None:
        with self.assertRaises(ValueError):
            SQLiteCache(
                db_path=os.path.join(self.tmpdir, "c.db"),
                table_name="x; DROP TABLE y",
            )

    def test_get_set_delete_and_no_connection_leak(self) -> None:
        path = os.path.join(self.tmpdir, "c.db")
        cache = SQLiteCache(db_path=path, table_name="cache")
        cache.set("k", "v", ttl=60)
        self.assertEqual(cache.get("k"), "v")
        self.assertTrue(cache.delete("k"))
        self.assertIsNone(cache.get("k"))

        # 连接应被显式关闭：删除文件不应因锁而失败
        os.remove(path)  # 若句柄泄漏，Windows 下这里会抛 PermissionError


class TestAdapterSessionThreadLocal(unittest.TestCase):
    def test_session_per_thread(self) -> None:
        adapter = MarketDataAdapter.__new__(MarketDataAdapter)
        adapter._session_local = threading.local()

        main_session = adapter._session
        self.assertIs(adapter._session, main_session)  # 同线程复用

        captured: dict = {}

        def worker() -> None:
            captured["session"] = adapter._session

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertIsNotNone(captured["session"])
        self.assertIsNot(
            captured["session"], main_session, "不同线程应使用不同 Session"
        )


class TestQuantWorkerSymbolsSnapshot(unittest.TestCase):
    def _make_worker(self) -> QuantWorker:
        worker = QuantWorker.__new__(QuantWorker)
        worker._lock = threading.Lock()
        worker.symbols = []
        return worker

    def test_empty_symbols(self) -> None:
        worker = self._make_worker()
        worker.set_symbols([])
        self.assertEqual(worker._symbols_snapshot(), [])

    def test_snapshot_is_copy(self) -> None:
        worker = self._make_worker()
        worker.set_symbols(["a", "b"])
        snap = worker._symbols_snapshot()
        snap.append("c")
        self.assertEqual(worker._symbols_snapshot(), ["a", "b"])

    def test_source_list_not_shared(self) -> None:
        worker = self._make_worker()
        src = ["x"]
        worker.set_symbols(src)
        src.append("y")  # 外部改动不应影响内部
        self.assertEqual(worker._symbols_snapshot(), ["x"])


if __name__ == "__main__":
    unittest.main()
