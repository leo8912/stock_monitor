"""
alert_text 量化预警推送文案纯函数单元测试
"""

import unittest

from stock_monitor.core.workers import alert_text


def _make_signal(sig_name="日线:MACD底背离", score=3, **overrides):
    sig = {
        "sig_name": sig_name,
        "score": score,
        "audit": {"label": "🟢 优质", "reasons": ["ROE稳定"], "score_offset": 1},
        "p_info": {"price": 1800.50, "pct": 1.2},
        "is_priority": False,
        "is_confluence": False,
    }
    sig.update(overrides)
    return sig


class TestFormatHistoryText(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(alert_text.format_history_text(None), "")
        self.assertEqual(alert_text.format_history_text([]), "")

    def test_recent_five(self):
        history = [{"time": f"1{i}:00", "name": f"信号{i}"} for i in range(7)]
        text = alert_text.format_history_text(history)
        self.assertTrue(text.startswith("\n今日轨迹："))
        # 只保留最近 5 条
        self.assertNotIn("信号0", text)
        self.assertNotIn("信号1", text)
        self.assertIn("信号2", text)
        self.assertIn("信号6", text)
        self.assertEqual(text.count("→"), 4)


class TestBuildDisplayLabels(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(
            alert_text.build_display_labels("贵州茅台", False, False),
            ("贵州茅台", ""),
        )

    def test_priority(self):
        self.assertEqual(
            alert_text.build_display_labels("贵州茅台", True, False),
            ("🔥 贵州茅台", " [精细关注]"),
        )

    def test_confluence_overrides_priority(self):
        self.assertEqual(
            alert_text.build_display_labels("贵州茅台", True, True),
            ("💎【策略共振】贵州茅台", " [超高可靠/重仓机会]"),
        )


class TestFormatBacktestStats(unittest.TestCase):
    def test_insufficient_data(self):
        self.assertEqual(alert_text.format_backtest_stats(None), "")
        self.assertEqual(alert_text.format_backtest_stats({}), "")
        self.assertEqual(alert_text.format_backtest_stats({"total_signals": 2}), "")

    def test_icons_by_win_rate(self):
        base = {"total_signals": 5, "avg_profit": 0.012}
        self.assertIn(
            "✅", alert_text.format_backtest_stats({**base, "win_rate": 0.65})
        )
        self.assertIn(
            "⚡", alert_text.format_backtest_stats({**base, "win_rate": 0.50})
        )
        self.assertIn("⚠️", alert_text.format_backtest_stats({**base, "win_rate": 0.30}))

    def test_format(self):
        stats = {"total_signals": 10, "win_rate": 0.6, "avg_profit": 0.025}
        text = alert_text.format_backtest_stats(stats)
        self.assertEqual(text, "\n历史复盘：✅ 同类评分胜率 60% (均益 +2.5%)")


class TestMergeSignalsText(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(alert_text.merge_signals_text("sh600519", "贵州茅台", [], []))

    def test_basic_merge(self):
        signals = [
            _make_signal(),
            _make_signal(sig_name="30分钟:OBV碎步吸筹", score=2),
        ]
        merged = alert_text.merge_signals_text("sh600519", "贵州茅台", signals, [])
        self.assertEqual(merged["title"], "🚨贵州茅台 (sh600519) +1.20%")
        self.assertEqual(merged["signals_text"], "检测到 2 个技术信号")
        self.assertEqual(merged["max_score"], 3)
        self.assertIn("日线:MACD底背离(+3)", merged["cycle_info"])
        self.assertIn("30分钟:OBV碎步吸筹(+2)", merged["cycle_info"])
        self.assertIn("🟢 优质 ROE稳定", merged["cycle_info"])
        self.assertNotIn("今日轨迹", merged["cycle_info"])

    def test_title_prefix_priority_and_confluence(self):
        priority = [_make_signal(is_priority=True)]
        merged = alert_text.merge_signals_text("sh600519", "贵州茅台", priority, [])
        self.assertTrue(merged["title"].startswith("🔥【精细关注】"))

        confluence = [_make_signal(is_priority=True, is_confluence=True)]
        merged = alert_text.merge_signals_text("sh600519", "贵州茅台", confluence, [])
        self.assertTrue(merged["title"].startswith("💎【策略共振】"))

    def test_missing_price(self):
        signals = [_make_signal(p_info={"price": 0, "pct": 0.0})]
        merged = alert_text.merge_signals_text("sh600519", "贵州茅台", signals, [])
        self.assertIn("(价格待更新)", merged["title"])

    def test_history_appended(self):
        history = [{"time": "10:30", "name": "日线:MACD底背离"}]
        merged = alert_text.merge_signals_text(
            "sh600519", "贵州茅台", [_make_signal()], history
        )
        self.assertIn("今日轨迹：10:30 日线:MACD底背离", merged["cycle_info"])

    def test_max_score_p_info_used(self):
        """价格信息取自最高分信号"""
        signals = [
            _make_signal(score=2, p_info={"price": 10.0, "pct": 2.0}),
            _make_signal(sig_name="S2", score=5, p_info={"price": 20.0, "pct": -1.0}),
        ]
        merged = alert_text.merge_signals_text("sh600519", "贵州茅台", signals, [])
        self.assertEqual(merged["p_info"], {"price": 20.0, "pct": -1.0})
        self.assertIn("-1.00%", merged["title"])


if __name__ == "__main__":
    unittest.main()
