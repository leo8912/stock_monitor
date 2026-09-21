"""
wave_report 波浪分析文案格式化函数单元测试
"""

import unittest
from unittest.mock import MagicMock

from stock_monitor.core.engine import wave_report
from stock_monitor.core.workers.quant_worker import QuantWorker


class TestWaveReport(unittest.TestCase):
    def test_get_prev_next_wave(self):
        self.assertEqual(wave_report.get_prev_next_wave("3"), ("2", "4"))
        self.assertEqual(wave_report.get_prev_next_wave("1"), ("C", "2"))
        self.assertEqual(wave_report.get_prev_next_wave("C"), ("B", "1"))

    def test_get_prev_next_wave_unknown(self):
        self.assertEqual(wave_report.get_prev_next_wave("X"), ("未知", "未知"))

    def test_resolve_sub_wave_empty(self):
        self.assertEqual(wave_report.resolve_sub_wave(None), ("", ""))
        res = MagicMock()
        res.current_wave = None
        self.assertEqual(wave_report.resolve_sub_wave(res), ("", ""))

    def test_resolve_sub_wave_with_result(self):
        res = MagicMock()
        res.current_wave = {"wave": "3", "desc": "主升"}
        self.assertEqual(wave_report.resolve_sub_wave(res), ("3", "主升"))

    def test_build_fib_support_resistance(self):
        levels = {"start": 8.0, "end": 12.0, "0.382": 9.5, "0.618": 10.5, "1.0": 12.0}
        support, resistance = wave_report.build_fib_support_resistance(levels, 10.0)
        self.assertIn("9.50", support)
        self.assertIn("10.50", resistance)
        self.assertIn("12.00", resistance)

    def test_build_fib_support_resistance_empty(self):
        support, resistance = wave_report.build_fib_support_resistance({}, 10.0)
        self.assertEqual((support, resistance), ("无", "无"))

    def test_format_wave_history_lines(self):
        waves = [
            {
                "duration_days": 5,
                "pct_change": 3.2,
                "direction": "up",
                "is_current": True,
                "label": "1浪",
                "from_date": "2026-09-01",
                "to_date": "2026-09-10",
            }
        ]
        lines = wave_report.format_wave_history_lines(waves)
        text = "\n".join(lines)
        self.assertIn("近期走势:", text)
        self.assertIn("+3.2%", text)
        self.assertIn("←当前位置", text)
        self.assertIn("09-01->09-10", text)

    def test_format_remaining_space_lines(self):
        rs = {
            "remaining_pct": 8.5,
            "target_price": 12.34,
            "basis": "斐波那契",
            "remaining_days_est": 10,
        }
        lines = wave_report.format_remaining_space_lines(rs)
        text = "\n".join(lines)
        self.assertIn("目标位: 12.34", text)
        self.assertIn("+8.5%", text)
        self.assertIn("约10个交易日", text)

    def test_explain_wave(self):
        self.assertEqual(wave_report.explain_wave("3", "bullish"), "主升浪，涨幅最大、速度最快的阶段")
        self.assertEqual(wave_report.explain_wave("3", None), "")
        self.assertEqual(wave_report.explain_wave("X", "bullish"), "")

    def test_wave_action_hint(self):
        self.assertEqual(wave_report.wave_action_hint("5", "bullish"), "建议: 逢高减仓，锁定利润")
        self.assertEqual(
            wave_report.wave_action_hint("X", None), "建议: 观望为主，等方向明确"
        )

    def test_format_wave_text_analysis_short_df(self):
        """数据不足时返回空字符串"""
        self.assertEqual(wave_report.format_wave_text_analysis("000001", "平安", "日线", None), "")


class TestQuantWorkerWaveDelegation(unittest.TestCase):
    """QuantWorker 的波浪文案辅助方法应委托给 wave_report 模块"""

    def test_static_delegation(self):
        self.assertEqual(
            QuantWorker._explain_wave("C", "bearish"), wave_report.explain_wave("C", "bearish")
        )
        self.assertEqual(
            QuantWorker._wave_action_hint("B", "bearish"),
            wave_report.wave_action_hint("B", "bearish"),
        )
        self.assertEqual(
            QuantWorker._resolve_sub_wave(None), wave_report.resolve_sub_wave(None)
        )

    def test_get_prev_next_wave_delegation(self):
        # 实例方法但不依赖实例状态，可传 None 验证委托逻辑
        self.assertEqual(
            QuantWorker._get_prev_next_wave(None, "A"),
            wave_report.get_prev_next_wave("A"),
        )


if __name__ == "__main__":
    unittest.main()
