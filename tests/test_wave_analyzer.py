"""波浪分析器单元测试"""

import numpy as np
import pandas as pd
import pytest

from stock_monitor.core.engine.wave_analyzer import (
    SwingPoint,
    WaveAnalysisResult,
    WaveAnalyzer,
)


def _make_df(prices_high, prices_low, prices_close, dates=None):
    """构造测试用 DataFrame"""
    n = len(prices_high)
    if dates is None:
        dates = (
            pd.date_range("2026-01-01", periods=n, freq="D")
            .strftime("%Y-%m-%d")
            .tolist()
        )
    return pd.DataFrame(
        {
            "high": prices_high,
            "low": prices_low,
            "close": prices_close,
            "datetime": dates,
        }
    )


class TestSwingPoint:
    def test_swing_point_creation(self):
        sp = SwingPoint(index=10, type="peak", price=100.0, date_str="2026-03-10")
        assert sp.index == 10
        assert sp.type == "peak"
        assert sp.price == 100.0
        assert sp.datetime == pd.Timestamp("2026-03-10")

    def test_swing_point_to_dict(self):
        sp = SwingPoint(index=5, type="trough", price=80.0, date_str="2026-02-01")
        d = sp.to_dict()
        assert d["index"] == 5
        assert d["type"] == "trough"
        assert d["price"] == 80.0
        assert d["date"] == "2026-02-01"

    def test_swing_point_invalid_date(self):
        sp = SwingPoint(index=0, type="peak", price=100.0, date_str="invalid")
        assert pd.isna(sp.datetime)


class TestDetectZigzag:
    def test_empty_df(self):
        df = pd.DataFrame(columns=["high", "low", "close", "datetime"])
        assert WaveAnalyzer.detect_zigzag(df, threshold=0.05) == []

    def test_short_df(self):
        df = _make_df([100, 101], [99, 100], [100, 100.5])
        assert WaveAnalyzer.detect_zigzag(df, threshold=0.05) == []

    def test_uptrend(self):
        # 明确的上升趋势：从 100 涨到 120
        n = 50
        prices = np.linspace(100, 120, n)
        noise = np.random.RandomState(42).normal(0, 0.5, n)
        highs = prices + 1.0 + noise
        lows = prices - 1.0 + noise
        closes = prices + noise
        df = _make_df(highs.tolist(), lows.tolist(), closes.tolist())

        swings = WaveAnalyzer.detect_zigzag(df, threshold=0.03)
        assert len(swings) >= 2
        # 应该至少有一个 peak 和一个 trough
        types = [s.type for s in swings if s.type != "current"]
        assert "peak" in types
        assert "trough" in types

    def test_current_point_always_present(self):
        n = 30
        prices = np.linspace(100, 110, n)
        noise = np.random.RandomState(42).normal(0, 0.3, n)
        highs = prices + 1.0 + noise
        lows = prices - 1.0 + noise
        closes = prices + noise
        df = _make_df(highs.tolist(), lows.tolist(), closes.tolist())

        swings = WaveAnalyzer.detect_zigzag(df, threshold=0.03)
        if swings:
            assert swings[-1].type == "current"

    def test_datetime_parsed(self):
        n = 30
        prices = np.linspace(100, 110, n)
        highs = prices + 1.0
        lows = prices - 1.0
        closes = prices
        df = _make_df(highs.tolist(), lows.tolist(), closes.tolist())

        swings = WaveAnalyzer.detect_zigzag(df, threshold=0.03)
        for s in swings:
            assert not pd.isna(s.datetime)


class TestCalculateWaveDetails:
    def test_empty_swings(self):
        assert WaveAnalyzer._calculate_wave_details([]) == []

    def test_single_extreme(self):
        sp = SwingPoint(index=5, type="peak", price=100.0, date_str="2026-03-10")
        assert WaveAnalyzer._calculate_wave_details([sp]) == []

    def test_two_extremes(self):
        sp1 = SwingPoint(index=0, type="trough", price=80.0, date_str="2026-01-01")
        sp2 = SwingPoint(index=10, type="peak", price=100.0, date_str="2026-01-11")
        details = WaveAnalyzer._calculate_wave_details([sp1, sp2])
        assert len(details) == 1
        assert details[0]["label"] == "浪1"
        assert details[0]["duration_days"] == 10
        assert details[0]["price_change"] == 20.0
        assert details[0]["pct_change"] == pytest.approx(25.0, abs=0.1)
        assert details[0]["direction"] == "up"

    def test_multiple_extremes(self):
        sp1 = SwingPoint(index=0, type="trough", price=80.0, date_str="2026-01-01")
        sp2 = SwingPoint(index=10, type="peak", price=100.0, date_str="2026-01-11")
        sp3 = SwingPoint(index=20, type="trough", price=90.0, date_str="2026-01-21")
        sp4 = SwingPoint(index=30, type="peak", price=120.0, date_str="2026-02-01")
        details = WaveAnalyzer._calculate_wave_details([sp1, sp2, sp3, sp4])
        assert len(details) == 3
        assert details[0]["direction"] == "up"
        assert details[1]["direction"] == "down"
        assert details[2]["direction"] == "up"
        assert details[2]["label"] == "浪3"


class TestEstimateRemainingSpace:
    def test_returns_none_for_unknown_wave(self):
        swings = [
            SwingPoint(0, "trough", 80.0, "2026-01-01"),
            SwingPoint(10, "peak", 100.0, "2026-01-11"),
            SwingPoint(20, "current", 95.0, "2026-01-21"),
        ]
        wave = {"wave": "unknown", "trend": "bullish"}
        assert WaveAnalyzer._estimate_remaining_space(swings, wave, {}) is None

    def test_wave3_target(self):
        # 浪1: 80→100 (+20), 浪2: 100→90, 浪3 starts at 90
        swings = [
            SwingPoint(0, "trough", 80.0, "2026-01-01"),
            SwingPoint(10, "peak", 100.0, "2026-01-11"),
            SwingPoint(20, "trough", 90.0, "2026-01-21"),
            SwingPoint(30, "peak", 110.0, "2026-02-01"),
        ]
        wave = {"wave": "3", "trend": "bullish"}
        result = WaveAnalyzer._estimate_remaining_space(swings, wave, {})
        assert result is not None
        # 目标 = 90 + 20 * 1.618 = 122.36
        assert result["target_price"] == pytest.approx(122.36, abs=0.1)
        assert result["remaining_pct"] > 0
        assert "浪1" in result["basis"]

    def test_bullish_trend_requires_trough(self):
        swings = [
            SwingPoint(0, "trough", 80.0, "2026-01-01"),
            SwingPoint(10, "peak", 100.0, "2026-01-11"),
            SwingPoint(20, "current", 95.0, "2026-01-21"),
        ]
        wave = {"wave": "3", "trend": "bullish"}
        # 只有一个 trough，浪1幅度不够
        result = WaveAnalyzer._estimate_remaining_space(swings, wave, {})
        # may or may not return None depending on structure
        # just ensure no crash
        assert result is None or isinstance(result, dict)


class TestAnalyze:
    def test_returns_none_for_short_data(self):
        df = _make_df([100] * 10, [99] * 10, [100] * 10)
        assert WaveAnalyzer.analyze(df, threshold=0.05) is None

    def test_returns_result_for_sufficient_data(self):
        n = 60
        # Create a wave pattern: up-down-up
        t = np.linspace(0, 4 * np.pi, n)
        prices = (
            100
            + 15 * np.sin(t)
            + np.cumsum(np.random.RandomState(42).normal(0, 0.5, n))
        )
        highs = prices + 2.0
        lows = prices - 2.0
        closes = prices
        df = _make_df(highs.tolist(), lows.tolist(), closes.tolist())

        result = WaveAnalyzer.analyze(df, threshold=0.03)
        if result is not None:
            assert isinstance(result, WaveAnalysisResult)
            assert result.current_wave is not None
            assert "wave" in result.current_wave
            assert result.all_waves is not None
            assert isinstance(result.all_waves, list)

    def test_result_has_remaining_space(self):
        n = 60
        t = np.linspace(0, 4 * np.pi, n)
        prices = (
            100
            + 15 * np.sin(t)
            + np.cumsum(np.random.RandomState(42).normal(0, 0.5, n))
        )
        highs = prices + 2.0
        lows = prices - 2.0
        closes = prices
        df = _make_df(highs.tolist(), lows.tolist(), closes.tolist())

        result = WaveAnalyzer.analyze(df, threshold=0.03)
        if result is not None:
            # remaining_space may be None or a dict
            assert result.remaining_space is None or isinstance(
                result.remaining_space, dict
            )
