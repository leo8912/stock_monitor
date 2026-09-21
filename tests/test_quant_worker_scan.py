"""
QuantWorker 扫描编排 characterization 测试

锁定 ``perform_scan`` / ``perform_scan_parallel`` / ``_scan_single_symbol``
的现有行为，为后续拆解提供安全网。所有行情/回测依赖均以 mock 替代，
不触发网络、数据库与真实缓存文件。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from stock_monitor.core.workers import scan_rules

CACHE_MODULE = "stock_monitor.core.workers.quant_worker"


def _make_worker(tmp_dir):
    """创建依赖全部 mock 化的 QuantWorker（引擎/回测器替换为 MagicMock）。"""
    from stock_monitor.core.workers.quant_worker import QuantWorker

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


def _engine_defaults(worker, signals=None, score=0, audit=None, rsrs_z=0.0):
    """配置 mock 引擎的默认返回值。"""
    worker.engine._parse_symbol.return_value = ("600519", 1, None)
    worker.engine.get_latest_price_info.return_value = {"price": 10.0, "pct": 1.0}
    worker.engine.fetch_bars.return_value = MagicMock(name="daily_df")
    worker.engine.scan_all_timeframes.return_value = list(signals) if signals else []
    worker.engine.detect_obv_accumulation.return_value = []
    worker.engine.calculate_rsrs.return_value = (rsrs_z, 0.01)
    worker.engine.calculate_intensity_score_with_symbol.return_value = (
        score,
        audit if audit is not None else {"label": ""},
    )
    worker.backtester.get_strategy_stats.return_value = None
    worker.fetcher.name_registry.get_name.return_value = "贵州茅台"


class TestScanSingleSymbol(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.worker = _make_worker(self.tmp_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_signals_low_score_returns_none(self):
        """无信号且评分低于门槛（默认 3）时不处理，返回 None"""
        _engine_defaults(self.worker, signals=[], score=2)
        with patch.object(self.worker, "_process_signals") as mock_process:
            result = self.worker._scan_single_symbol("sh600519")
        self.assertIsNone(result)
        mock_process.assert_not_called()

    def test_signals_trigger_process(self):
        """有信号时调用 _process_signals 并透传其结果"""
        signals = [{"name": "MACD 底背离", "tf": "Daily", "time": "10:00"}]
        _engine_defaults(self.worker, signals=signals, score=3)
        self.worker.engine.calculate_rsrs.return_value = (0.0, 0.01)  # 无共振

        with patch.object(
            self.worker, "_process_signals", return_value={"symbol": "sh600519"}
        ) as mock_process:
            result = self.worker._scan_single_symbol("sh600519")

        self.assertEqual(result, {"symbol": "sh600519"})
        mock_process.assert_called_once()
        args = mock_process.call_args.args
        self.assertEqual(args[0], "sh600519")  # symbol
        self.assertEqual(args[1], "贵州茅台")  # stock_name
        self.assertEqual(args[2], signals)  # signals
        self.assertEqual(args[3], 3)  # score
        self.assertEqual(args[6], False)  # is_priority
        self.assertEqual(args[7], False)  # is_confluence
        # cached_daily_df 透传日线数据
        self.assertIs(args[8], self.worker.engine.fetch_bars.return_value)

    def test_obv_signals_appended(self):
        """OBV 吸筹信号以固定格式追加到信号列表"""
        _engine_defaults(self.worker, signals=[], score=5)
        self.worker.engine.detect_obv_accumulation.return_value = [
            {"level": "日线", "time": "10:30"}
        ]
        with patch.object(self.worker, "_process_signals", return_value=None) as m:
            self.worker._scan_single_symbol("sh600519")
        signals = m.call_args.args[2]
        self.assertIn(
            {"name": "OBV 低位累积 (日线)", "tf": "Daily", "time": "10:30"},
            signals,
        )

    def test_confluence_detected(self):
        """MACD 底背离 + RSRS zscore > 0.7 触发策略共振，评分至少为 4"""
        signals = [{"name": "MACD 底背离", "tf": "Daily", "time": "10:00"}]
        _engine_defaults(self.worker, signals=signals, score=2, rsrs_z=0.8)
        with patch.object(self.worker, "_process_signals", return_value=None) as m:
            self.worker._scan_single_symbol("sh600519")
        args = m.call_args.args
        self.assertTrue(args[7])  # is_confluence
        self.assertEqual(args[3], 4)  # score = max(2, 4)
        names = [s["name"] for s in args[2]]
        self.assertIn("⚡策略共振 (底背离+RSRS)", names)

    def test_no_confluence_when_rsrs_low(self):
        """RSRS zscore <= 0.7 时不构成共振"""
        signals = [{"name": "MACD 底背离", "tf": "Daily", "time": "10:00"}]
        _engine_defaults(self.worker, signals=signals, score=3, rsrs_z=0.7)
        with patch.object(self.worker, "_process_signals", return_value=None) as m:
            self.worker._scan_single_symbol("sh600519")
        args = m.call_args.args
        self.assertFalse(args[7])  # is_confluence
        self.assertEqual(args[3], 3)  # 评分不被抬升

    def test_priority_lowers_threshold(self):
        """高历史胜率标的（胜率>=80%且信号数>=3）门槛降为 2 并带胜率标签"""
        _engine_defaults(self.worker, signals=[], score=2)
        self.worker.backtester.get_strategy_stats.return_value = {
            "total_signals": 5,
            "win_rate": 0.85,
        }
        with patch.object(self.worker, "_process_signals", return_value=None) as m:
            self.worker._scan_single_symbol("sh600519")
        args = m.call_args.args
        self.assertTrue(args[6])  # is_priority
        names = [s["name"] for s in args[2]]
        self.assertIn("多因子综合走强 [💎 历史胜率 85%]", names)

    def test_non_priority_threshold_three(self):
        """普通标的门槛为 3：评分 2 无信号时不处理"""
        _engine_defaults(self.worker, signals=[], score=2)
        self.worker.backtester.get_strategy_stats.return_value = {
            "total_signals": 5,
            "win_rate": 0.5,
        }
        with patch.object(self.worker, "_process_signals") as m:
            result = self.worker._scan_single_symbol("sh600519")
        self.assertIsNone(result)
        m.assert_not_called()

    def test_multi_factor_signal_without_wr_label(self):
        """无回测数据时多因子信号不带胜率标签"""
        _engine_defaults(self.worker, signals=[], score=3)
        with patch.object(self.worker, "_process_signals", return_value=None) as m:
            self.worker._scan_single_symbol("sh600519")
        names = [s["name"] for s in m.call_args.args[2]]
        self.assertIn("多因子综合走强", names)

    def test_exception_returns_none(self):
        """扫描过程异常时记录日志并返回 None，不向外抛出"""
        _engine_defaults(self.worker)
        self.worker.engine.scan_all_timeframes.side_effect = RuntimeError("boom")
        result = self.worker._scan_single_symbol("sh600519")
        self.assertIsNone(result)


class TestPerformScanParallel(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.worker = _make_worker(self.tmp_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_symbols_emits_both_signals(self):
        """空标的列表：发出 scan_started/scan_finished 后直接返回"""
        self.worker.symbols = []
        events = []
        self.worker.scan_started.connect(lambda: events.append("start"))
        self.worker.scan_finished.connect(lambda: events.append("finish"))

        with patch.object(self.worker, "_scan_single_symbol") as mock_scan:
            self.worker.perform_scan_parallel()

        self.assertEqual(events, ["start", "finish"])
        mock_scan.assert_not_called()

    def test_scans_all_symbols_and_emits(self):
        """所有标的均被扫描，信号各发出一次"""
        self.worker.symbols = ["sh600519", "sz000001", "sz000002"]
        events = []
        self.worker.scan_started.connect(lambda: events.append("start"))
        self.worker.scan_finished.connect(lambda: events.append("finish"))

        with patch.object(
            self.worker, "_scan_single_symbol", return_value=None
        ) as mock_scan:
            self.worker.perform_scan_parallel()

        self.assertEqual(events, ["start", "finish"])
        self.assertEqual(mock_scan.call_count, 3)
        scanned = {c.args[0] for c in mock_scan.call_args_list}
        self.assertEqual(scanned, set(self.worker.symbols))

    def test_symbol_failure_isolated(self):
        """单个标的扫描异常不影响其余标的，scan_finished 仍发出"""
        self.worker.symbols = ["sh600519", "sz000001"]
        events = []
        self.worker.scan_finished.connect(lambda: events.append("finish"))

        def side_effect(symbol):
            if symbol == "sh600519":
                raise RuntimeError("scan boom")
            return {"symbol": symbol, "signals": ["X"]}

        with patch.object(
            self.worker, "_scan_single_symbol", side_effect=side_effect
        ) as mock_scan:
            self.worker.perform_scan_parallel()

        self.assertEqual(mock_scan.call_count, 2)
        self.assertEqual(events, ["finish"])

    def test_uses_snapshot_copy(self):
        """扫描使用标的快照：扫描期间主线程替换列表不影响本轮"""
        self.worker.set_symbols(["sh600519"])
        scanned = []

        def side_effect(symbol):
            scanned.append(symbol)
            # 模拟扫描期间主线程修改标的列表
            self.worker.set_symbols(["sz000001", "sz000002"])
            return None

        with patch.object(self.worker, "_scan_single_symbol", side_effect=side_effect):
            self.worker.perform_scan_parallel()

        self.assertEqual(scanned, ["sh600519"])

    def test_perform_scan_delegates_to_parallel(self):
        """perform_scan 串行兼容入口委托并行版本"""
        with patch.object(self.worker, "perform_scan_parallel") as mock_parallel:
            self.worker.perform_scan()
        mock_parallel.assert_called_once()

    def test_timeout_still_emits_scan_finished(self):
        """整体超时（as_completed 抛 TimeoutError）时 scan_finished 仍必须发出

        回归背景：超时异常发生在 for 循环本身，旧代码会跳过 scan_finished，
        导致 UI 的"扫描中"状态永不复位。
        """
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        self.worker.symbols = ["sh600519", "sz000001"]
        events = []
        self.worker.scan_started.connect(lambda: events.append("start"))
        self.worker.scan_finished.connect(lambda: events.append("finish"))

        def fake_as_completed(futures, timeout=None):
            raise FuturesTimeoutError()

        with (
            patch(
                "stock_monitor.core.workers.quant_worker.as_completed",
                side_effect=fake_as_completed,
            ),
            patch.object(self.worker, "_scan_single_symbol"),
        ):
            self.worker.perform_scan_parallel()  # 不应抛出

        self.assertEqual(events, ["start", "finish"])


class TestScanRules(unittest.TestCase):
    """scan_rules 纯决策函数单元测试"""

    def test_append_obv_signals(self):
        signals = []
        result = scan_rules.append_obv_signals(
            signals, [{"level": "日线", "time": "10:00"}]
        )
        self.assertIs(result, signals)  # 原地追加，保持引用
        self.assertEqual(
            signals[0],
            {"name": "OBV 低位累积 (日线)", "tf": "Daily", "time": "10:00"},
        )

    def test_append_obv_signals_empty(self):
        signals = [{"name": "X"}]
        self.assertEqual(scan_rules.append_obv_signals(signals, []), signals)

    def test_is_confluence(self):
        div = [{"name": "MACD 底背离"}]
        self.assertTrue(scan_rules.is_confluence(div, 0.71))
        self.assertFalse(scan_rules.is_confluence(div, 0.7))  # 严格大于
        self.assertFalse(scan_rules.is_confluence(div, 0.5))
        self.assertFalse(scan_rules.is_confluence([{"name": "其他"}], 0.9))

    def test_is_priority_symbol(self):
        stats = {"total_signals": 5, "win_rate": 0.85}
        self.assertEqual(
            scan_rules.is_priority_symbol(stats), (True, " [💎 历史胜率 85%]")
        )
        # 样本不足
        self.assertEqual(
            scan_rules.is_priority_symbol({"total_signals": 2, "win_rate": 0.9}),
            (False, ""),
        )
        # 胜率不足
        self.assertEqual(
            scan_rules.is_priority_symbol({"total_signals": 5, "win_rate": 0.7}),
            (False, ""),
        )
        self.assertEqual(scan_rules.is_priority_symbol(None), (False, ""))
        self.assertEqual(scan_rules.is_priority_symbol({}), (False, ""))

    def test_apply_confluence(self):
        signals, score = scan_rules.apply_confluence([], 2)
        self.assertEqual(score, 4)
        self.assertEqual(signals[0]["name"], scan_rules.CONFLUENCE_SIGNAL_NAME)
        self.assertEqual(signals[0]["tf"], "Daily")

        signals, score = scan_rules.apply_confluence([], 5)
        self.assertEqual(score, 5)  # 已高于 4 不抬升

    def test_append_multi_factor_fallback(self):
        signals = scan_rules.append_multi_factor_fallback([], 3, 3, " [标签]")
        self.assertEqual(signals[0]["name"], "多因子综合走强 [标签]")

        # 未达门槛不追加
        self.assertEqual(scan_rules.append_multi_factor_fallback([], 2, 3, ""), [])
        # 已有信号不追加
        self.assertEqual(
            scan_rules.append_multi_factor_fallback([{"name": "X"}], 5, 3, ""),
            [{"name": "X"}],
        )


if __name__ == "__main__":
    unittest.main()
