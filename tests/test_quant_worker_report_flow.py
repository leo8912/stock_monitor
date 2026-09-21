"""
QuantWorker 复盘报告生成流程 characterization 测试

锁定 ``generate_daily_summary_report`` 的编排行为与
``_analyze_symbol_for_report`` / ``_collect_report_signals`` 的过滤规则。
所有依赖 mock 化，不触网、不触库、不触真实缓存文件。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

CACHE_MODULE = "stock_monitor.core.workers.quant_worker"


def _make_worker():
    from stock_monitor.core.workers.quant_worker import QuantWorker

    mock_fetcher = MagicMock()
    mock_fetcher.market_adapter = MagicMock()
    mock_fetcher.name_registry = MagicMock()

    tmp = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp.name)
    try:
        with (
            patch(f"{CACHE_MODULE}.SIGNAL_CACHE_FILE", tmp_dir / "signal_cache.json"),
            patch(f"{CACHE_MODULE}.CACHE_DIR", tmp_dir),
            patch("stock_monitor.data.stock.stock_db.StockDatabase"),
        ):
            worker = QuantWorker(mock_fetcher, "https://test.webhook")
    except Exception:
        tmp.cleanup()
        raise
    worker.engine = MagicMock()
    worker.backtester = MagicMock()
    worker.config = {"auto_export_excel": True}
    return worker, tmp


def _signal_info(symbol="sh600519", name="贵州茅台", score=3):
    return {
        "symbol": symbol,
        "name": name,
        "signals": ["MACD 底背离"],
        "score": score,
        "audit": {"label": ""},
        "price": 10.0,
        "pct": 1.0,
        "wave_daily": None,
        "wave_60m": None,
    }


class TestGenerateDailySummaryReport(unittest.TestCase):
    def setUp(self):
        self.worker, self._tmp = _make_worker()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_symbols_skips_report(self):
        """无自选股：直接跳过，不收集、不发送、不导出"""
        self.worker.symbols = []
        with (
            patch.object(self.worker, "_collect_report_signals") as mock_collect,
            patch.object(self.worker, "_send_report_and_wave_text") as mock_send,
            patch.object(self.worker, "_auto_export_stocks") as mock_export,
        ):
            self.worker.generate_daily_summary_report("manual")

        mock_collect.assert_not_called()
        mock_send.assert_not_called()
        mock_export.assert_not_called()

    def test_normal_flow(self):
        """正常流程：收集 → 标题/内容 → 发送 → 自动导出"""
        self.worker.set_symbols(["sh600519", "sz000001"])
        all_signals = [_signal_info()]
        strong = [all_signals[0]]

        with (
            patch.object(
                self.worker,
                "_collect_report_signals",
                return_value=(all_signals, strong),
            ) as mock_collect,
            patch.object(self.worker, "_get_report_title", return_value="标题"),
            patch.object(
                self.worker, "_format_report_content", return_value="内容"
            ) as mock_format,
            patch.object(self.worker, "_send_report_and_wave_text") as mock_send,
            patch.object(self.worker, "_auto_export_stocks") as mock_export,
        ):
            self.worker.generate_daily_summary_report("manual")

        mock_collect.assert_called_once_with(["sh600519", "sz000001"])
        mock_format.assert_called_once_with("标题", all_signals, strong, "manual")
        mock_send.assert_called_once_with("manual", "标题", "内容", all_signals)
        mock_export.assert_called_once_with(["sh600519", "sz000001"])

    def test_uses_symbols_snapshot(self):
        """报告生成使用标的快照：生成期间主线程替换列表不影响本轮"""
        self.worker.set_symbols(["sh600519"])
        captured = {}

        def fake_collect(symbols):
            captured["symbols"] = list(symbols)
            # 模拟生成期间主线程修改列表
            self.worker.set_symbols(["sz000001"])
            return [], []

        with (
            patch.object(
                self.worker, "_collect_report_signals", side_effect=fake_collect
            ),
            patch.object(self.worker, "_format_report_content", return_value=""),
            patch.object(self.worker, "_auto_export_stocks") as mock_export,
        ):
            self.worker.generate_daily_summary_report("auto")

        self.assertEqual(captured["symbols"], ["sh600519"])
        mock_export.assert_called_once_with(["sh600519"])  # 导出同样用快照

    def test_empty_content_skips_send(self):
        """内容为空时不发送，但自动导出仍执行"""
        self.worker.set_symbols(["sh600519"])
        with (
            patch.object(self.worker, "_collect_report_signals", return_value=([], [])),
            patch.object(self.worker, "_format_report_content", return_value=""),
            patch.object(self.worker, "_send_report_and_wave_text") as mock_send,
            patch.object(self.worker, "_auto_export_stocks") as mock_export,
        ):
            self.worker.generate_daily_summary_report("auto")

        mock_send.assert_not_called()
        mock_export.assert_called_once()

    def test_empty_config_skips_send(self):
        """config 为空字典（falsy）时不发送"""
        self.worker.set_symbols(["sh600519"])
        self.worker.config = {}
        with (
            patch.object(
                self.worker,
                "_collect_report_signals",
                return_value=([_signal_info()], [_signal_info()]),
            ),
            patch.object(self.worker, "_format_report_content", return_value="内容"),
            patch.object(self.worker, "_send_report_and_wave_text") as mock_send,
            patch.object(self.worker, "_auto_export_stocks"),
        ):
            self.worker.generate_daily_summary_report("auto")

        mock_send.assert_not_called()

    def test_collect_exception_caught(self):
        """收集阶段异常被捕获：不发送、不导出、不外泄"""
        self.worker.set_symbols(["sh600519"])
        with (
            patch.object(
                self.worker,
                "_collect_report_signals",
                side_effect=RuntimeError("collect boom"),
            ),
            patch.object(self.worker, "_send_report_and_wave_text") as mock_send,
            patch.object(self.worker, "_auto_export_stocks") as mock_export,
        ):
            self.worker.generate_daily_summary_report("auto")  # 不应抛出

        mock_send.assert_not_called()
        mock_export.assert_not_called()

    def test_webhook_override(self):
        """manual 使用自定义 webhook，其余走默认配置"""
        self.assertEqual(
            self.worker._webhook_override("manual"), "https://test.webhook"
        )
        self.assertIsNone(self.worker._webhook_override("auto"))
        self.assertIsNone(self.worker._webhook_override("morning"))


class TestAnalyzeSymbolForReport(unittest.TestCase):
    def setUp(self):
        self.worker, self._tmp = _make_worker()
        self.worker.engine._parse_symbol.return_value = ("600519", 1, None)
        self.worker.engine.get_latest_price_info.return_value = {
            "price": 10.0,
            "pct": 1.0,
        }
        self.worker.fetcher.name_registry.get_name.return_value = "贵州茅台"

    def tearDown(self):
        self._tmp.cleanup()

    def _set_daily_df(self, rows: int):
        df = MagicMock()
        df.empty = False
        df.__len__.return_value = rows
        self.worker.engine.fetch_bars.return_value = df
        return df

    def test_short_df_returns_none(self):
        """日线数据不足 50 根返回 None"""
        self._set_daily_df(49)
        self.assertIsNone(self.worker._analyze_symbol_for_report("sh600519"))

    def test_no_signals_returns_none(self):
        """无技术信号返回 None"""
        self._set_daily_df(100)
        self.worker.engine.scan_all_timeframes.return_value = []
        self.worker.engine.detect_obv_accumulation.return_value = []
        self.assertIsNone(self.worker._analyze_symbol_for_report("sh600519"))

    def test_normal_signal_info(self):
        """有信号时返回完整信息字典"""
        self._set_daily_df(100)
        signals = [{"name": "MACD 底背离", "tf": "Daily", "time": "10:00"}]
        self.worker.engine.scan_all_timeframes.return_value = signals
        self.worker.engine.detect_obv_accumulation.return_value = []
        self.worker.engine.calculate_intensity_score_with_symbol.return_value = (
            4,
            {"label": "🟢 优质"},
        )
        # 波浪分析返回 None（mock 掉 WaveAnalyzer 调用路径）
        with patch(
            "stock_monitor.core.engine.wave_analyzer.WaveAnalyzer.analyze",
            return_value=None,
        ):
            info = self.worker._analyze_symbol_for_report("sh600519")

        self.assertIsNotNone(info)
        self.assertEqual(info["symbol"], "sh600519")
        self.assertEqual(info["name"], "贵州茅台")
        self.assertEqual(info["signals"], ["MACD 底背离"])
        self.assertEqual(info["score"], 4)
        self.assertEqual(info["audit"], {"label": "🟢 优质"})
        self.assertEqual(info["price"], 10.0)
        self.assertEqual(info["pct"], 1.0)
        self.assertIsNone(info["wave_daily"])
        self.assertIsNone(info["wave_60m"])

    def test_obv_signals_appended(self):
        """OBV 吸筹信号被转换为标准格式并计入报告信号列表。

        回归背景：旧代码直接 ``signals.extend(obv_signals)``，OBV 原始字典
        （无 name 键）导致后续 ``s["name"]`` KeyError 被捕获，持有 OBV 吸筹
        信号的股票被静默排除出复盘报告。
        """
        self._set_daily_df(100)
        self.worker.engine.scan_all_timeframes.return_value = [
            {"name": "MACD 底背离", "tf": "Daily", "time": "10:00"}
        ]
        self.worker.engine.detect_obv_accumulation.return_value = [
            {"level": "日线", "time": "10:30"}
        ]
        self.worker.engine.calculate_intensity_score_with_symbol.return_value = (
            3,
            {"label": ""},
        )
        with patch(
            "stock_monitor.core.engine.wave_analyzer.WaveAnalyzer.analyze",
            return_value=None,
        ):
            info = self.worker._analyze_symbol_for_report("sh600519")

        self.assertIsNotNone(info)
        self.assertIn("MACD 底背离", info["signals"])
        self.assertIn("OBV 低位累积 (日线)", info["signals"])

    def test_exception_returns_none(self):
        """引擎异常时返回 None"""
        self._set_daily_df(100)
        self.worker.engine.scan_all_timeframes.side_effect = RuntimeError("boom")
        self.assertIsNone(self.worker._analyze_symbol_for_report("sh600519"))


class TestCollectReportSignals(unittest.TestCase):
    def setUp(self):
        self.worker, self._tmp = _make_worker()

    def tearDown(self):
        self._tmp.cleanup()

    def test_collect_splits_by_score(self):
        """全部信号与强信号（score >= 3）分离"""
        weak = _signal_info("sz000001", "平安银行", score=2)
        strong1 = _signal_info("sh600519", "贵州茅台", score=3)
        strong2 = _signal_info("sz000002", "万科A", score=5)

        with patch.object(
            self.worker,
            "_analyze_symbol_for_report",
            side_effect=[weak, strong1, strong2],
        ):
            all_signals, strong_signals = self.worker._collect_report_signals(
                ["sz000001", "sh600519", "sz000002"]
            )

        self.assertEqual(len(all_signals), 3)
        self.assertEqual(strong_signals, [strong1, strong2])

    def test_none_results_skipped(self):
        """分析失败（None）的标的被跳过"""
        ok = _signal_info()
        with patch.object(
            self.worker,
            "_analyze_symbol_for_report",
            side_effect=[None, ok, None],
        ):
            all_signals, strong_signals = self.worker._collect_report_signals(
                ["a", "b", "c"]
            )

        self.assertEqual(all_signals, [ok])
        self.assertEqual(strong_signals, [ok])


if __name__ == "__main__":
    unittest.main()

