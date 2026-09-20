"""T12 除零防护回归测试

验证 5 处除零风险点在任何输入下都不会抛 ``ZeroDivisionError``：
- ``core/engine/wave_analyzer.py``：当前价为 0
- ``core/engine/backtest_engine.py``：入场价为 0
- ``ui/dialogs/stock_comparison_dialog.py``：昨收价为 0（表达式守卫）
- ``ui/widgets/taskbar_quote_bar.py``：空股票列表
- ``ui/widgets/tray_quote_panel.py``：每页数量为 0
"""

import unittest
from unittest.mock import MagicMock

import pandas as pd

from stock_monitor.core.engine.backtest_engine import BacktestEngine
from stock_monitor.core.engine.quant_engine import QuantEngine
from stock_monitor.core.engine.wave_analyzer import SwingPoint, WaveAnalyzer
from stock_monitor.ui.widgets.taskbar_quote_bar import TaskbarQuoteBar
from stock_monitor.ui.widgets.tray_quote_panel import TrayQuotePanel


class TestWaveAnalyzerDivisionGuard(unittest.TestCase):
    """当前价为 0 时不得除零。"""

    @staticmethod
    def _swings():
        return [
            SwingPoint(index=0, type="trough", price=10.0, date_str="2026-01-01"),
            SwingPoint(index=1, type="peak", price=12.0, date_str="2026-01-10"),
        ]

    def test_zero_current_price_returns_none(self):
        # 当前价为 0：必须安全返回 None，而不是 ZeroDivisionError
        result = WaveAnalyzer._estimate_remaining_space(
            self._swings(),
            {"wave": "3", "trend": "bullish"},
            {},
            actual_current_price=0.0,
        )
        self.assertIsNone(result)

    def test_positive_current_price_computes(self):
        result = WaveAnalyzer._estimate_remaining_space(
            self._swings(),
            {"wave": "3", "trend": "bullish"},
            {},
            actual_current_price=11.0,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result["remaining_pct"], float)


class TestBacktestDivisionGuard(unittest.TestCase):
    """入场价为 0 的信号点必须被跳过。"""

    def test_zero_entry_price_is_skipped(self):
        engine = BacktestEngine(MagicMock(spec=QuantEngine))
        engine._save_cache = MagicMock()  # 避免写入真实缓存文件

        n = 200
        closes = [10.0] * n
        closes[100] = 0.0  # 除零陷阱：某根 K 线 close=0
        df = pd.DataFrame(
            {
                "open": closes,
                "high": [c + 1.0 for c in closes],
                "low": [max(c - 1.0, 0.0) for c in closes],
                "close": closes,
                "vol": [100.0] * n,
            }
        )

        engine.qe.fetch_bars.return_value = df
        # 仅让 idx=100 命中信号（其 entry_price=0）
        engine.qe.check_macd_bullish_divergence.side_effect = (
            lambda _df, window=None, end_idx=0: end_idx == 100
        )

        result = engine.get_strategy_stats("000001", 1, 9)

        # 不应抛异常；唯一的信号点因入场价为 0 被跳过 → 0 胜率
        self.assertIsNotNone(result)
        self.assertEqual(result["total_signals"], 1)
        self.assertEqual(result["win_rate"], 0.0)


class TestTaskbarEmptyStocksGuard(unittest.TestCase):
    """空股票列表时 _paint_page 立即返回，不触碰 height()/除法。"""

    def test_paint_page_with_empty_stocks_returns_immediately(self):
        class _Dummy:
            def height(self):  # pragma: no cover - 不应被调用
                raise AssertionError("空股票列表不应调用 height()")

        painter = MagicMock()
        # 不应抛异常，也不应触碰 height()（即 rowh = height()/len(stocks) 不执行）
        TaskbarQuoteBar._paint_page(_Dummy(), painter, [], 0.0, 1.0)


class TestTrayPanelPerPageGuard(unittest.TestCase):
    """每页数量为 0 时按 1 处理，避免 // 除零。"""

    def test_zero_per_page_defaults_to_one(self):
        class _Dummy:
            _all_stocks = [1, 2, 3]
            _per_page = 0

        self.assertEqual(TrayQuotePanel._page_count(_Dummy()), 3)

    def test_normal_per_page(self):
        class _Dummy:
            _all_stocks = [1, 2, 3, 4, 5]
            _per_page = 2

        self.assertEqual(TrayQuotePanel._page_count(_Dummy()), 3)


if __name__ == "__main__":
    unittest.main()
