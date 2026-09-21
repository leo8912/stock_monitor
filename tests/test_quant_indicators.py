"""
quant_indicators 纯指标计算函数单元测试
"""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from stock_monitor.core.engine import quant_indicators
from stock_monitor.core.engine.quant_engine import QuantEngine


def _make_ohlcv(n: int, start: float = 10.0, step: float = 0.05) -> pd.DataFrame:
    """构造单调上升的 OHLCV 数据"""
    close = start + np.arange(n) * step
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )


class TestQuantIndicators(unittest.TestCase):
    def test_check_bbands_squeeze_short_df(self):
        """数据不足 100 根时返回 False"""
        df = _make_ohlcv(50)
        self.assertFalse(quant_indicators.check_bbands_squeeze(df))

    def test_check_bbands_squeeze_no_bbb_column(self):
        """缺少 BBB_ 列时返回 False"""
        df = _make_ohlcv(120)
        self.assertFalse(quant_indicators.check_bbands_squeeze(df))

    def test_check_bbands_squeeze_with_column(self):
        """带宽等于近 100 根最小值时判定为收窄"""
        df = _make_ohlcv(120)
        df["BBB_20_2.0"] = np.linspace(10.0, 1.0, 120)
        self.assertTrue(quant_indicators.check_bbands_squeeze(df))
        df2 = _make_ohlcv(120)
        df2["BBB_20_2.0"] = np.linspace(1.0, 10.0, 120)
        self.assertFalse(quant_indicators.check_bbands_squeeze(df2))

    def test_check_macd_bullish_divergence_short_df(self):
        """数据不足 window*2 时返回 False"""
        df = _make_ohlcv(30)
        self.assertFalse(quant_indicators.check_macd_bullish_divergence(df))

    def test_calculate_rsrs_insufficient_data(self):
        """数据不足时返回 (0.0, 0.0)"""
        df = _make_ohlcv(30)
        zscore, slope = quant_indicators.calculate_rsrs(df)
        self.assertEqual((zscore, slope), (0.0, 0.0))

    def test_calculate_rsrs_returns_tuple(self):
        """数据充足时返回 (zscore, slope) 浮点元组"""
        df = _make_ohlcv(200)
        zscore, slope = quant_indicators.calculate_rsrs(df, n=18, m=60)
        self.assertIsInstance(zscore, float)
        self.assertIsInstance(slope, float)
        # 单调上升数据 slope 应为正
        self.assertGreater(slope, 0)

    def test_check_accumulation_short_df(self):
        """数据不足 20 根时返回 False"""
        df = _make_ohlcv(10)
        df["OBV"] = np.arange(10.0)
        self.assertFalse(quant_indicators.check_accumulation(df))

    def test_check_accumulation_low_volatility_rising_obv(self):
        """低波动 + OBV 走强时判定为吸筹"""
        df = _make_ohlcv(30, start=10.0, step=0.0)
        df["high"] = df["close"] + 0.01
        df["low"] = df["close"] - 0.01
        # 前 20 根 OBV 平稳，最近 5 根快速抬升（5日均值 > 区间均值 * 1.05）
        obv = np.full(30, 100.0)
        obv[-5:] = [115, 116, 117, 118, 119]
        df["OBV"] = obv
        self.assertTrue(quant_indicators.check_accumulation(df))

    def test_check_accumulation_high_volatility(self):
        """高波动区间不判定为吸筹"""
        df = _make_ohlcv(30, start=10.0, step=0.0)
        df["high"] = df["close"] + 1.0
        df["low"] = df["close"] - 1.0
        df["OBV"] = np.arange(30.0)
        self.assertFalse(quant_indicators.check_accumulation(df))

    def test_calculate_comprehensive_indicators_empty(self):
        """空数据或不足 60 根返回空字典"""
        self.assertEqual(quant_indicators.calculate_comprehensive_indicators(pd.DataFrame()), {})
        self.assertEqual(quant_indicators.calculate_comprehensive_indicators(_make_ohlcv(30)), {})


class TestQuantEngineDelegation(unittest.TestCase):
    """QuantEngine 方法应委托给 quant_indicators 模块函数"""

    def setUp(self):
        self.engine = QuantEngine(MagicMock())

    def test_calculate_rsrs_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators, "calculate_rsrs", return_value=(1.5, 0.5)
        ) as mock_fn:
            self.assertEqual(self.engine.calculate_rsrs(df, n=18, m=60), (1.5, 0.5))
            mock_fn.assert_called_once_with(df, n=18, m=60)

    def test_check_bbands_squeeze_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators, "check_bbands_squeeze", return_value=True
        ) as mock_fn:
            self.assertTrue(self.engine.check_bbands_squeeze(df, end_idx=5))
            mock_fn.assert_called_once_with(df, 5)

    def test_check_macd_bullish_divergence_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators, "check_macd_bullish_divergence", return_value=True
        ) as mock_fn:
            self.assertTrue(self.engine.check_macd_bullish_divergence(df, window=10))
            mock_fn.assert_called_once_with(df, 10, None)

    def test_check_accumulation_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators, "check_accumulation", return_value=False
        ) as mock_fn:
            self.assertFalse(self.engine.check_accumulation(df, end_idx=3))
            mock_fn.assert_called_once_with(df, 3)

    def test_get_bbands_position_desc_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators, "get_bbands_position_desc", return_value=" 🟢 下轨支撑"
        ) as mock_fn:
            self.assertEqual(self.engine.get_bbands_position_desc(df), " 🟢 下轨支撑")
            mock_fn.assert_called_once_with(df)

    def test_calculate_comprehensive_indicators_delegates(self):
        df = _make_ohlcv(10)
        with patch.object(
            quant_indicators,
            "calculate_comprehensive_indicators",
            return_value={"trend": "🔴 多头"},
        ) as mock_fn:
            self.assertEqual(
                self.engine.calculate_comprehensive_indicators(df), {"trend": "🔴 多头"}
            )
            mock_fn.assert_called_once_with(df)


if __name__ == "__main__":
    unittest.main()
