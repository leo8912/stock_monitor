"""
signal_cache 信号缓存持久化纯函数单元测试
"""

import json
import tempfile
import unittest
from pathlib import Path

from stock_monitor.core.workers import signal_cache


class TestParseCachePayload(unittest.TestCase):
    def test_new_format(self):
        now = 1000.0
        data = {
            "SH600000::Daily:MACD底背离": {"last_score": 3, "last_push_ts": now - 10},
        }
        last_time, states, expired = signal_cache.parse_cache_payload(data, now, 86400)
        key = ("SH600000", "Daily:MACD底背离")
        self.assertEqual(expired, 0)
        self.assertEqual(states[key]["last_score"], 3)
        self.assertEqual(last_time[key], now - 10)

    def test_old_format_timestamp_only(self):
        now = 1000.0
        data = {"SZ000001::Daily:RSI超卖": now - 100}
        last_time, states, expired = signal_cache.parse_cache_payload(data, now, 86400)
        key = ("SZ000001", "Daily:RSI超卖")
        self.assertEqual(expired, 0)
        self.assertEqual(last_time[key], now - 100)
        self.assertNotIn(key, states)

    def test_expired_entries_removed(self):
        now = 100000.0
        data = {
            "A::sig1": now - 10,  # 未过期
            "B::sig2": now - 90000,  # 已过期（旧格式）
            "C::sig3": {
                "last_score": 1,
                "last_push_ts": now - 90000,
            },  # 已过期（新格式）
        }
        last_time, states, expired = signal_cache.parse_cache_payload(data, now, 86400)
        self.assertEqual(expired, 2)
        self.assertEqual(list(last_time.keys()), [("A", "sig1")])
        self.assertEqual(states, {})

    def test_malformed_key_skipped(self):
        data = {"no-separator": 123.0, "A::sig": 456.0}
        last_time, states, expired = signal_cache.parse_cache_payload(
            data, 1000.0, 86400
        )
        self.assertEqual(len(last_time), 1)
        self.assertIn(("A", "sig"), last_time)

    def test_new_format_missing_ts_defaults_zero_and_expires(self):
        data = {"A::sig": {"last_score": 1}}  # 无 last_push_ts -> 0 -> 过期
        last_time, states, expired = signal_cache.parse_cache_payload(
            data, 100000.0, 86400
        )
        self.assertEqual(expired, 1)
        self.assertEqual(last_time, {})
        self.assertEqual(states, {})


class TestBuildCachePayload(unittest.TestCase):
    def test_roundtrip_key_format(self):
        states = {
            ("SH600000", "Daily:MACD底背离"): {"last_score": 3, "last_push_ts": 1.0},
            ("SZ000001", "Daily:RSI超卖"): {"last_score": 2, "last_push_ts": 2.0},
        }
        payload = signal_cache.build_cache_payload(states)
        self.assertEqual(
            set(payload.keys()),
            {"SH600000::Daily:MACD底背离", "SZ000001::Daily:RSI超卖"},
        )
        self.assertEqual(payload["SH600000::Daily:MACD底背离"]["last_score"], 3)


class TestAtomicWriteJson(unittest.TestCase):
    def test_write_and_no_tmp_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "signal_cache.json"
            data = {"A::sig": {"last_score": 1, "last_push_ts": 1.0}}
            signal_cache.atomic_write_json(path, data)

            self.assertTrue(path.exists())
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, data)
            # 临时文件已清理
            self.assertEqual(list(Path(tmp).glob("*.tmp*")), [])

    def test_unicode_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "signal_cache.json"
            data = {"平安银行::日线:底背离": 1.0}
            signal_cache.atomic_write_json(path, data)
            with open(path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), data)


class TestQuantWorkerSignalCacheDelegation(unittest.TestCase):
    """QuantWorker 缓存方法应使用 signal_cache 模块并保持可 patch 的路径常量"""

    def test_worker_methods_delegate(self):
        import time
        from unittest.mock import MagicMock, patch

        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache_file = cache_dir / "signal_cache.json"
            with (
                patch(
                    "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
                    cache_file,
                ),
                patch("stock_monitor.core.workers.quant_worker.CACHE_DIR", cache_dir),
                patch("stock_monitor.data.stock.stock_db.StockDatabase"),
            ):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")
                now = time.time()
                worker._signal_states[("SH600000", "Daily:X")] = {
                    "last_score": 1,
                    "last_push_ts": now,
                }
                worker._save_signal_cache()
                self.assertTrue(cache_file.exists())

                worker2_states = worker._signal_states
                worker._signal_states = {}
                worker._load_signal_cache()
                self.assertIn(("SH600000", "Daily:X"), worker._signal_states)
                self.assertEqual(worker._last_signal_time[("SH600000", "Daily:X")], now)
                del worker2_states


if __name__ == "__main__":
    unittest.main()
