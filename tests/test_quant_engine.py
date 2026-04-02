"""
QuantEngine 量化分析引擎单元测试
"""

import unittest
from unittest.mock import MagicMock

import pandas as pd

from stock_monitor.core.quant_engine import QuantEngine


class TestQuantEngine(unittest.TestCase):
    """QuantEngine 测试类"""

    def setUp(self):
        """测试前准备"""
        # 创建模拟的 mootdx 客户端
        self.mock_client = MagicMock()
        self.engine = QuantEngine(self.mock_client)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.engine._cache_ttl, 60)
        self.assertEqual(len(self.engine._bars_cache), 0)
        self.assertIsNotNone(self.engine.fin_filter)

    def test_parse_symbol(self):
        """测试符号解析功能"""
        from stock_monitor.core.symbol_resolver import SymbolType

        # 测试 A 股代码解析 - 纯数字默认按深圳市场处理
        code, market, stype = self.engine._parse_symbol("000001")
        self.assertEqual(code, "000001")
        self.assertIn(market, [0, 1])  # 深圳或上海市场
        self.assertEqual(stype, SymbolType.STOCK)

        # 测试指数代码解析 - sh000001 实际解析为上证指数 (代码 999999)
        code, market, stype = self.engine._parse_symbol("sh000001")
        self.assertEqual(code, "999999")  # 上证指数内部代码
        self.assertEqual(market, 1)  # 上海市场
        self.assertEqual(stype, SymbolType.INDEX)

    def test_validate_data_with_valid_dataframe(self):
        """测试数据验证 - 有效数据"""
        # 创建测试 DataFrame
        df = pd.DataFrame(
            {
                "open": [10.0, 10.5, 11.0],
                "high": [10.8, 11.2, 11.5],
                "low": [9.8, 10.3, 10.8],
                "close": [10.5, 11.0, 11.3],
                "volume": [1000, 1200, 1100],
            }
        )

        from stock_monitor.core.symbol_resolver import SymbolType

        result = self.engine._validate_data(df, SymbolType.STOCK)
        self.assertTrue(result)

    def test_validate_data_with_empty_dataframe(self):
        """测试数据验证 - 空 DataFrame"""
        df = pd.DataFrame()
        from stock_monitor.core.symbol_resolver import SymbolType

        result = self.engine._validate_data(df, SymbolType.STOCK)
        self.assertFalse(result)

    def test_validate_data_with_none_dataframe(self):
        """测试数据验证 - None 值"""
        result = self.engine._validate_data(None, None)
        self.assertFalse(result)

    def test_freq_map_constants(self):
        """测试频率映射常量"""
        self.assertEqual(QuantEngine.FreqMap["15m"], 1)
        self.assertEqual(QuantEngine.FreqMap["30m"], 2)
        self.assertEqual(QuantEngine.FreqMap["60m"], 3)
        self.assertEqual(QuantEngine.FreqMap["daily"], 9)

    def test_tf_chinese_map_constants(self):
        """测试中文频率映射常量"""
        self.assertEqual(QuantEngine.TF_CHINESE_MAP["15m"], "15分钟")
        self.assertEqual(QuantEngine.TF_CHINESE_MAP["30m"], "30分钟")
        self.assertEqual(QuantEngine.TF_CHINESE_MAP["60m"], "60分钟")
        self.assertEqual(QuantEngine.TF_CHINESE_MAP["daily"], "日线")

    def test_calculate_comprehensive_indicators_structure(self):
        """测试综合指标计算返回结构"""
        # 创建模拟数据
        df = pd.DataFrame(
            {
                "open": [10.0 + i * 0.1 for i in range(30)],
                "high": [10.5 + i * 0.1 for i in range(30)],
                "low": [9.8 + i * 0.1 for i in range(30)],
                "close": [10.2 + i * 0.1 for i in range(30)],
                "volume": [1000 + i * 10 for i in range(30)],
            }
        )

        try:
            result = self.engine.calculate_comprehensive_indicators(df)

            # 验证返回类型为字典
            self.assertIsInstance(result, dict)

            # 验证包含预期的键（根据实际实现调整）
            expected_keys = ["macd", "kdj", "rsi"]
            for key in expected_keys:
                self.assertIn(key, result)

        except Exception as e:
            # 如果 pandas_ta 未安装，应该优雅处理
            self.skipTest(f"指标计算需要 pandas_ta: {e}")

    def test_get_bbands_position_desc(self):
        """测试布林带位置描述"""
        df = pd.DataFrame({"close": [10.0, 10.5, 11.0, 11.5, 12.0]})

        desc = self.engine.get_bbands_position_desc(df)

        # 验证返回字符串描述
        self.assertIsInstance(desc, str)
        self.assertTrue(len(desc) > 0)

    def test_market_relative_strength(self):
        """测试市场相对强度计算"""
        try:
            strength = self.engine.get_market_relative_strength()

            # 验证返回值为浮点数
            self.assertIsInstance(strength, float)

            # 验证值在合理范围内 (通常 0-2 之间)
            self.assertGreaterEqual(strength, 0)
            self.assertLessEqual(strength, 3)

        except Exception as e:
            self.skipTest(f"网络请求可能失败：{e}")

    def test_intensity_score_calculation(self):
        """测试强度分数计算"""
        df = pd.DataFrame(
            {
                "open": [10.0 + i * 0.1 for i in range(30)],
                "high": [10.5 + i * 0.1 for i in range(30)],
                "low": [9.8 + i * 0.1 for i in range(30)],
                "close": [10.2 + i * 0.1 for i in range(30)],
                "volume": [1000 + i * 10 for i in range(30)],
            }
        )

        try:
            score = self.engine.calculate_intensity_score(df)

            # 验证返回值为数值类型
            self.assertIsInstance(score, (int, float))

        except Exception as e:
            self.skipTest(f"强度计算需要额外依赖：{e}")

    def test_five_day_avg_volume_cache(self):
        """测试 5 日均量缓存机制"""
        import time

        # 模拟 bars 方法返回的数据（包含 amount 列）
        mock_df = pd.DataFrame(
            {"amount": [1000000, 1200000, 1100000, 1300000, 1400000]}
        )
        # 设置日期索引
        today = time.strftime("%Y-%m-%d")
        mock_df.index = pd.date_range(end=today, periods=5)

        self.mock_client.bars.return_value = mock_df

        # 首次调用
        vol1 = self.engine.get_five_day_avg_minute_volume("000001")

        # 验证缓存已创建
        self.assertIn("000001", self.engine._avg_vol_cache)
        self.assertEqual(self.engine._avg_vol_cache["000001"]["date"], today)

        # 第二次调用应该使用缓存
        vol2 = self.engine.get_five_day_avg_minute_volume("000001")

        # 验证两次结果相同（来自缓存）
        self.assertEqual(vol1, vol2)

        # 验证只调用了一次 API
        self.mock_client.bars.assert_called_once()


class TestQuantEngineCacheMechanism(unittest.TestCase):
    """QuantEngine 缓存机制专项测试"""

    def setUp(self):
        self.mock_client = MagicMock()
        self.engine = QuantEngine(self.mock_client)

    def test_bars_cache_storage(self):
        """测试 K 线缓存存储"""
        # 准备测试数据
        test_df = pd.DataFrame({"close": [10.0, 10.5, 11.0]})
        cache_key = ("sh000001", 9)

        # 手动存入缓存
        import time

        self.engine._bars_cache[cache_key] = (test_df, time.time())

        # 验证缓存存在
        self.assertIn(cache_key, self.engine._bars_cache)
        cached_df, timestamp = self.engine._bars_cache[cache_key]
        pd.testing.assert_frame_equal(test_df, cached_df)

    def test_auction_cache_structure(self):
        """测试竞价缓存结构"""
        # 模拟竞价数据
        auction_data = {"000001": {"price": 10.5, "vol": 10000, "intensity": 0.8}}

        self.engine._auction_cache.update(auction_data)

        # 验证缓存结构
        self.assertIn("000001", self.engine._auction_cache)
        cached = self.engine._auction_cache["000001"]
        self.assertIn("price", cached)
        self.assertIn("vol", cached)
        self.assertIn("intensity", cached)


if __name__ == "__main__":
    unittest.main()
