"""ponytail-review 回归：防抖占位回滚、扫描代际、mootdx 切片、BAT 转义。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from stock_monitor.core.app_update.downloader import _parse_content_range_start
from stock_monitor.core.app_update.installer import _bat_escape
from stock_monitor.core.cache_manager import LRUCache
from stock_monitor.core.data.market_data_adapter import MarketDataAdapter
from stock_monitor.core.workers.quant_worker import QuantWorker

CACHE_MODULE = "stock_monitor.core.workers.quant_worker"


def _make_worker(tmp_dir: Path) -> QuantWorker:
    mock_fetcher = MagicMock()
    mock_fetcher.market_adapter = MagicMock()
    mock_fetcher.name_registry = MagicMock()
    with (
        patch(f"{CACHE_MODULE}.SIGNAL_CACHE_FILE", tmp_dir / "signal_cache.json"),
        patch(f"{CACHE_MODULE}.CACHE_DIR", tmp_dir),
        patch("stock_monitor.data.stock.stock_db.StockDatabase"),
    ):
        worker = QuantWorker(mock_fetcher, "https://test.webhook")
    worker.engine = MagicMock()
    worker.backtester = MagicMock()
    worker.config = {}
    return worker


class TestBarsSliceDirection(unittest.TestCase):
    """mootdx 语义：start=从最新往回偏移，offset=取多少条。"""

    def setUp(self):
        with patch("easyquotation.use", return_value=MagicMock()):
            self.adapter = MarketDataAdapter()
        self.df = __import__("pandas").DataFrame(
            {"close": list(range(10))}  # 0..9 升序，最新=9
        )
        patcher = patch.object(
            self.adapter, "_fetch_tencent_kline", return_value=self.df
        )
        self.mock_fetch = patcher.start()
        self.addCleanup(patcher.stop)

    def test_start_zero_equals_tail(self):
        out = self.adapter.bars("600000", 1, category=9, start=0, offset=3)
        self.assertEqual(out["close"].tolist(), [7, 8, 9])

    def test_start_drops_newest_bars(self):
        # 10 根升序 0..9；start=2 丢弃最新 2 根(8,9)后取 3 根 → 5,6,7
        out = self.adapter.bars("600000", 1, category=9, start=2, offset=3)
        self.assertEqual(out["close"].tolist(), [5, 6, 7])

    def test_start_beyond_length_returns_empty(self):
        out = self.adapter.bars("600000", 1, category=9, start=20, offset=3)
        self.assertTrue(out.empty)


class TestLRUTtlOverride(unittest.TestCase):
    def test_override_uses_written_at_not_default_ttl(self):
        import time as _time

        def _seed():
            cache = LRUCache(max_size=10, default_ttl=3600)
            cache.set("k", "v")
            past = _time.time() - 100
            with cache._lock:
                value, _expiry, _written_at = cache._cache["k"]
                cache._cache["k"] = (value, _time.time() + 3600, past)
            return cache

        # override=50 < 已写入 100s → 按 written_at+50 已过期并删除
        self.assertIsNone(_seed().get("k", ttl_override=50))
        # override=200 > 100 → 仍命中
        self.assertEqual(_seed().get("k", ttl_override=200), "v")


class TestContentRangeStart(unittest.TestCase):
    def test_parse_valid(self):
        self.assertEqual(_parse_content_range_start("bytes 100-999/1234"), 100)

    def test_parse_invalid_returns_none(self):
        self.assertIsNone(_parse_content_range_start("bytes */1234"))
        self.assertIsNone(_parse_content_range_start(""))


class TestBatEscape(unittest.TestCase):
    def test_percent_doubled_bang_kept(self):
        self.assertEqual(_bat_escape(r"C:\50%!x!"), r"C:\50%%!x!")


class TestPushPlaceholderRollback(unittest.TestCase):
    def test_failed_push_clears_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            worker = _make_worker(Path(td))
            worker.engine.get_market_relative_strength.return_value = (0.0, True)
            worker.backtester.get_score_stats.return_value = None
            symbol, sig = "sh600000", "日线:测试信号"
            worker._signal_states[(symbol, sig)] = {
                "last_score": 2,
                "last_push_ts": 1.0,
            }
            ps = [
                {
                    "sig_name": sig,
                    "score": 2,
                    "p_info": {"pct": 1.0},
                    "is_priority": False,
                    "is_confluence": False,
                    "reason": "新信号",
                    "sig": {"name": "x", "tf": "Daily"},
                    "audit": {},
                }
            ]
            with patch(
                f"{CACHE_MODULE}.NotifierService.dispatch_alert",
                side_effect=RuntimeError("webhook down"),
            ):
                triggered = worker._push_individual_signals(symbol, "测试", ps, "", "")
            self.assertEqual(triggered, [])
            self.assertNotIn((symbol, sig), worker._signal_states)

    def test_failed_merged_push_clears_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            worker = _make_worker(Path(td))
            symbol = "sh600000"
            names = ["日线:A", "日线:B"]
            ps = [
                {
                    "sig_name": n,
                    "score": 3,
                    "p_info": {},
                    "is_priority": False,
                    "is_confluence": False,
                    "reason": "新信号",
                    "sig": {"name": "x", "tf": "Daily"},
                    "audit": {},
                }
                for n in names
            ]
            for n in names:
                worker._signal_states[(symbol, n)] = {
                    "last_score": 3,
                    "last_push_ts": 1.0,
                }
            worker._merge_signals_for_symbol = MagicMock(
                return_value={
                    "title": f"t ({symbol})",
                    "signals_text": "s",
                    "cycle_info": "c",
                    "p_info": {},
                }
            )
            with patch(
                f"{CACHE_MODULE}.NotifierService.dispatch_alert",
                side_effect=RuntimeError("webhook down"),
            ):
                triggered = worker._push_merged_signals(symbol, "测试", ps, "", "")
            self.assertEqual(triggered, [])
            for n in names:
                self.assertNotIn((symbol, n), worker._signal_states)


class TestScanGenerationGuard(unittest.TestCase):
    def test_stale_generation_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            worker = _make_worker(Path(td))
            worker._scan_generation = 5
            self.assertIsNone(worker._scan_single_symbol("sh600000", scan_gen=4))


if __name__ == "__main__":
    unittest.main()
