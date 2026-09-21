"""
quant_report 复盘报告文案格式化函数单元测试
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from stock_monitor.core.engine import quant_report
from stock_monitor.core.workers.quant_worker import QuantWorker


def _make_signal(**overrides):
    sig = {
        "name": "平安银行",
        "symbol": "SZ000001",
        "signals": ["MACD底背离"],
        "score": 3,
        "price": 12.34,
        "pct": 1.5,
        "audit": {"label": "财报健康"},
    }
    sig.update(overrides)
    return sig


class TestGetReportTitle(unittest.TestCase):
    def test_known_types(self):
        now = datetime(2026, 9, 21, 11, 35)
        self.assertEqual(
            quant_report.get_report_title("morning", now),
            "📊 早盘复盘 (2026-09-21 11:35)",
        )
        self.assertEqual(
            quant_report.get_report_title("afternoon", now),
            "📈 午盘复盘 (2026-09-21 11:35)",
        )
        self.assertEqual(
            quant_report.get_report_title("manual", now),
            "🔍 全量复盘 (2026-09-21 11:35)",
        )
        self.assertEqual(
            quant_report.get_report_title("auto", now), "📉 自动复盘 (2026-09-21 11:35)"
        )

    def test_unknown_type_falls_back_to_auto(self):
        now = datetime(2026, 9, 21, 15, 5)
        self.assertEqual(
            quant_report.get_report_title("whatever", now),
            "📉 自动复盘 (2026-09-21 15:05)",
        )


class TestFormatReportContent(unittest.TestCase):
    def test_no_signals(self):
        self.assertEqual(
            quant_report.format_report_content("标题", [], [], "manual"),
            "今日无显著信号",
        )

    def test_basic_content(self):
        signals = [_make_signal()]
        content = quant_report.format_report_content("复盘", signals, [], "manual")
        self.assertIn("**复盘**", content)
        self.assertIn("总信号数：1", content)
        self.assertIn("平安银行", content)
        self.assertIn("￥12.34 (+1.5%)", content)
        self.assertIn("📋 全部信号", content)
        self.assertNotIn("🌟 重点关注", content)

    def test_strong_signals_section(self):
        strong = [
            _make_signal(
                wave_daily={"desc": "3浪主升", "wave": "3"},
                wave_60m={"desc": "2浪回调", "wave": "2"},
            )
        ]
        content = quant_report.format_report_content("复盘", strong, strong, "auto")
        self.assertIn("🌟 重点关注", content)
        self.assertIn("🌊日线:3浪主升", content)
        self.assertIn("🌊60m:2浪回调", content)
        self.assertIn("(日线:3浪)", content)
        self.assertIn("(60m:2浪)", content)
        self.assertIn("财报健康", content)

    def test_sorted_by_score_desc(self):
        signals = [
            _make_signal(name="低分", score=1),
            _make_signal(name="高分", score=5),
        ]
        content = quant_report.format_report_content("复盘", signals, [], "manual")
        self.assertLess(content.index("高分"), content.index("低分"))

    def test_zero_price_shows_placeholder(self):
        signals = [_make_signal(price=0, pct=0)]
        content = quant_report.format_report_content("复盘", signals, [], "manual")
        self.assertIn("--", content)


class TestQuantWorkerReportDelegation(unittest.TestCase):
    """QuantWorker 报告方法应委托给 quant_report 模块"""

    def test_get_report_title_delegates(self):
        with patch.object(
            quant_report, "get_report_title", return_value="T"
        ) as mock_fn:
            self.assertEqual(QuantWorker._get_report_title(None, "manual"), "T")
            mock_fn.assert_called_once_with("manual")

    def test_format_report_content_delegates(self):
        all_s, strong_s = [MagicMock()], [MagicMock()]
        with patch.object(
            quant_report, "format_report_content", return_value="C"
        ) as mock_fn:
            result = QuantWorker._format_report_content(
                None, "T", all_s, strong_s, "auto"
            )
            self.assertEqual(result, "C")
            mock_fn.assert_called_once_with("T", all_s, strong_s, "auto")


if __name__ == "__main__":
    unittest.main()
