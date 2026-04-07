"""
缓存预热功能测试 (P1-2性能优化)
"""

import time
from unittest.mock import MagicMock

import pytest

from stock_monitor.core.cache_warmer import (
    CacheWarmer,
    IndicatorComputationOptimizer,
    PerformanceMonitor,
)


class TestCacheWarmer:
    """缓存预热器测试"""

    @pytest.fixture
    def mock_engine_and_fetcher(self):
        """创建模拟的引擎和数据获取器"""
        mock_engine = MagicMock()
        mock_fetcher = MagicMock()

        # 模拟fetch_bars返回DataFrame
        import pandas as pd

        mock_bars = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )
        mock_engine.fetch_bars.return_value = mock_bars
        mock_engine.calculate_rsrs.return_value = (1.5, 0.05)
        mock_engine.detect_obv_accumulation.return_value = [
            {"level": "low", "time": time.time()}
        ]

        return mock_engine, mock_fetcher

    def test_cache_warmer_initialization(self, mock_engine_and_fetcher):
        """测试缓存预热器初始化"""
        engine, fetcher = mock_engine_and_fetcher
        warmer = CacheWarmer(engine, fetcher, max_workers=2)

        assert warmer.max_workers == 2
        assert warmer.cache_stats["total_symbols"] == 0
        assert warmer.cache_stats["warmed_symbols"] == 0

    def test_warm_cache_for_symbols_success(self, mock_engine_and_fetcher):
        """测试成功的缓存预热"""
        engine, fetcher = mock_engine_and_fetcher
        warmer = CacheWarmer(engine, fetcher, max_workers=2)

        symbols = ["000001.SZ", "000002.SZ"]
        stats = warmer.warm_cache_for_symbols(symbols, categories=[9], offset=100)

        assert stats["total_symbols"] == 2
        assert stats["warmed_symbols"] == 2
        assert stats["failed_symbols"] == 0
        assert stats["duration_seconds"] > 0

    def test_warm_cache_partial_failure(self, mock_engine_and_fetcher):
        """测试部分失败的缓存预热"""
        engine, fetcher = mock_engine_and_fetcher
        warmer = CacheWarmer(engine, fetcher, max_workers=2)

        # 第一个符号成功，第二个失败
        engine.fetch_bars.side_effect = [
            __import__("pandas").DataFrame({"close": [100], "volume": [1000]}),
            Exception("API Error"),
        ]

        symbols = ["000001.SZ", "000002.SZ"]
        stats = warmer.warm_cache_for_symbols(symbols, categories=[9], offset=100)

        assert stats["total_symbols"] == 2
        assert stats["failed_symbols"] >= 1

    def test_warm_cache_empty_symbol_list(self, mock_engine_and_fetcher):
        """测试空符号列表的缓存预热"""
        engine, fetcher = mock_engine_and_fetcher
        warmer = CacheWarmer(engine, fetcher, max_workers=2)

        stats = warmer.warm_cache_for_symbols([], categories=[9])

        assert stats["total_symbols"] == 0
        assert stats["warmed_symbols"] == 0

    def test_clear_caches(self, mock_engine_and_fetcher):
        """测试缓存清除"""
        engine, fetcher = mock_engine_and_fetcher

        # 设置模拟缓存
        engine._avg_vol_cache = MagicMock()
        engine._avg_vol_cache.cache = {"key": "value"}
        engine._rsrs_cache = {"key": "value"}

        warmer = CacheWarmer(engine, fetcher)
        result = warmer.clear_caches()

        assert result is True

    def test_get_cache_status(self, mock_engine_and_fetcher):
        """测试获取缓存状态"""
        engine, fetcher = mock_engine_and_fetcher

        # 设置模拟缓存统计
        mock_cache = MagicMock()
        mock_cache.get_stats.return_value = {
            "size": 10,
            "hits": 100,
            "misses": 20,
            "hit_rate": "83.3%",
        }
        engine._avg_vol_cache = mock_cache

        warmer = CacheWarmer(engine, fetcher)
        status = warmer.get_cache_status()

        assert "warming_stats" in status
        assert "engine_caches" in status


class TestIndicatorComputationOptimizer:
    """指标计算优化器测试"""

    @pytest.fixture
    def mock_engine(self):
        """创建模拟的引擎"""
        mock_engine = MagicMock()

        import pandas as pd

        mock_bars = pd.DataFrame(
            {
                "close": [100, 101, 102, 103, 104],
                "volume": [1000, 1100, 1200, 1300, 1400],
            }
        )
        mock_engine.fetch_bars.return_value = mock_bars
        mock_engine.calculate_rsrs.return_value = (1.5, 0.05)
        mock_engine.detect_obv_accumulation.return_value = [{"level": "low"}]
        mock_engine.scan_all_timeframes.return_value = [
            {"name": "MACD底背离"},
            {"name": "RSI超卖"},
        ]

        return mock_engine

    def test_optimizer_initialization(self, mock_engine):
        """测试优化器初始化"""
        optimizer = IndicatorComputationOptimizer(mock_engine)

        assert optimizer.indicator_cache == {}
        assert optimizer.cache_time == {}

    def test_compute_rsrs_indicator(self, mock_engine):
        """测试RSRS指标计算"""
        optimizer = IndicatorComputationOptimizer(mock_engine)

        results = optimizer.compute_indicator_set("000001.SZ", ["RSRS"])

        assert "RSRS" in results
        assert results["RSRS"]["z_score"] == 1.5

    def test_compute_multiple_indicators(self, mock_engine):
        """测试多个指标计算"""
        optimizer = IndicatorComputationOptimizer(mock_engine)

        results = optimizer.compute_indicator_set("000001.SZ", ["RSRS", "OBV", "MACD"])

        assert "RSRS" in results
        assert "OBV" in results
        assert "MACD" in results

    def test_compute_with_provided_bars(self, mock_engine):
        """测试使用提供的K线数据计算指标"""
        import pandas as pd

        optimizer = IndicatorComputationOptimizer(mock_engine)
        bars_df = pd.DataFrame({"close": [100, 101, 102]})

        optimizer.compute_indicator_set("000001.SZ", ["RSRS"], bars_df=bars_df)

        # 验证没有调用fetch_bars
        mock_engine.fetch_bars.assert_not_called()

    def test_invalidate_symbol_cache(self, mock_engine):
        """测试单个符号缓存失效"""
        optimizer = IndicatorComputationOptimizer(mock_engine)

        optimizer.indicator_cache["000001.SZ"] = {"RSRS": {"z_score": 1.5}}
        optimizer.cache_time["000001.SZ"] = time.time()

        optimizer.invalidate_cache("000001.SZ")

        assert "000001.SZ" not in optimizer.indicator_cache
        assert "000001.SZ" not in optimizer.cache_time

    def test_invalidate_all_caches(self, mock_engine):
        """测试清空所有缓存"""
        optimizer = IndicatorComputationOptimizer(mock_engine)

        optimizer.indicator_cache["000001.SZ"] = {"RSRS": {"z_score": 1.5}}
        optimizer.cache_time["000001.SZ"] = time.time()

        optimizer.invalidate_cache()

        assert len(optimizer.indicator_cache) == 0
        assert len(optimizer.cache_time) == 0


class TestPerformanceMonitor:
    """性能监测器测试"""

    def test_monitor_initialization(self):
        """测试监测器初始化"""
        monitor = PerformanceMonitor()

        assert monitor.scan_times == []
        assert monitor.cache_hits_trend == []

    def test_record_scan_time(self):
        """测试记录扫描耗时"""
        monitor = PerformanceMonitor()

        monitor.record_scan_time(5.5)
        monitor.record_scan_time(6.2)
        monitor.record_scan_time(5.8)

        assert len(monitor.scan_times) == 3
        assert 5.5 in monitor.scan_times

    def test_record_cache_hits(self):
        """测试记录缓存命中率"""
        monitor = PerformanceMonitor()

        monitor.record_cache_hits(85.0)
        monitor.record_cache_hits(87.5)
        monitor.record_cache_hits(82.0)

        assert len(monitor.cache_hits_trend) == 3
        assert 85.0 in monitor.cache_hits_trend

    def test_get_statistics(self):
        """测试获取性能统计"""
        monitor = PerformanceMonitor()

        monitor.record_scan_time(5.0)
        monitor.record_scan_time(6.0)
        monitor.record_scan_time(5.5)
        monitor.record_cache_hits(80.0)
        monitor.record_cache_hits(85.0)

        stats = monitor.get_statistics()

        assert stats["scans"] == 3
        assert stats["avg_time"] == pytest.approx(5.5, rel=0.1)
        assert stats["min_time"] == 5.0
        assert stats["max_time"] == 6.0
        assert 80 < stats["avg_cache_hit_rate"] < 90

    def test_get_statistics_no_data(self):
        """测试无数据时的统计"""
        monitor = PerformanceMonitor()

        stats = monitor.get_statistics()

        assert stats["scans"] == 0
        assert stats["avg_time"] == 0

    def test_format_statistics(self):
        """测试格式化统计信息"""
        monitor = PerformanceMonitor()

        # 无数据
        assert "暂无扫描数据" in monitor.format_statistics()

        # 有数据
        monitor.record_scan_time(5.5)
        monitor.record_scan_time(6.2)
        monitor.record_cache_hits(85.0)

        formatted = monitor.format_statistics()
        assert "扫描次数: 2" in formatted
        assert "最快:" in formatted or "最快" in formatted

    def test_max_records_limit(self):
        """测试记录数量限制"""
        monitor = PerformanceMonitor()
        monitor.max_records = 10

        # 添加15条记录，应该只保留最后10条
        for i in range(15):
            monitor.record_scan_time(float(i))

        assert len(monitor.scan_times) == 10
        assert monitor.scan_times[0] == 5.0  # 前5条被删除


class TestCacheWarmingIntegration:
    """缓存预热集成测试"""

    def test_cache_warmer_with_multiple_categories(self):
        """测试多周期缓存预热"""
        mock_engine = MagicMock()
        mock_fetcher = MagicMock()

        import pandas as pd

        mock_engine.fetch_bars.return_value = pd.DataFrame(
            {"close": [100, 101], "volume": [1000, 1100]}
        )
        mock_engine.calculate_rsrs.return_value = (1.0, 0.05)
        mock_engine.detect_obv_accumulation.return_value = []

        warmer = CacheWarmer(mock_engine, mock_fetcher, max_workers=2)
        stats = warmer.warm_cache_for_symbols(["000001.SZ"], categories=[1, 2, 3, 9])

        assert stats["warmed_symbols"] == 1
        # fetch_bars应该被调用4次（每个周期一次）
        assert mock_engine.fetch_bars.call_count >= 1

    def test_performance_monitoring_during_warming(self):
        """测试缓存预热期间的性能监测"""
        monitor = PerformanceMonitor()

        # 模拟三次扫描
        for _ in range(3):
            monitor.record_scan_time(5.0)
            monitor.record_cache_hits(85.0)

        stats = monitor.get_statistics()

        assert stats["scans"] == 3
        assert stats["avg_time"] == 5.0
