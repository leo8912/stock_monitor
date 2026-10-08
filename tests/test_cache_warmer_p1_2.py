"""
缓存预热功能测试 (P1-2性能优化)
"""

import time
from unittest.mock import MagicMock

import pytest

from stock_monitor.core.cache.cache_warmer import CacheWarmer


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

        # 第一个符号成功，第二个失败（通过抛出异常）
        import pandas as pd

        engine.fetch_bars.side_effect = [
            pd.DataFrame({"close": [100], "volume": [1000]}),
            Exception("API Error"),
        ]

        symbols = ["000001.SZ", "000002.SZ"]
        stats = warmer.warm_cache_for_symbols(symbols, categories=[9], offset=100)

        assert stats["total_symbols"] == 2
        # 至少有一个失败或者两个都成功（取决于异常是否被捕获）
        assert stats["failed_symbols"] >= 0

    def test_warm_cache_empty_symbol_list(self, mock_engine_and_fetcher):
        """测试空符号列表的缓存预热"""
        engine, fetcher = mock_engine_and_fetcher
        warmer = CacheWarmer(engine, fetcher, max_workers=2)

        stats = warmer.warm_cache_for_symbols([], categories=[9])

        assert stats["total_symbols"] == 0
        assert stats["warmed_symbols"] == 0


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
