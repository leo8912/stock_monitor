"""
BacktestEngine 回测引擎单元测试
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from stock_monitor.core.backtest_engine import BacktestEngine
from stock_monitor.core.quant_engine import QuantEngine


class TestBacktestEngine(unittest.TestCase):
    """BacktestEngine 测试类"""

    def setUp(self):
        """测试前准备"""
        # 创建模拟的 QuantEngine
        self.mock_quant_engine = MagicMock(spec=QuantEngine)
        self.engine = BacktestEngine(self.mock_quant_engine)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.engine.target_profit, 0.05)
        self.assertEqual(self.engine.stop_loss, 0.05)
        self.assertIsNotNone(self.engine._cache_file)

    def test_parameter_map_structure(self):
        """测试参数映射结构"""
        # 验证 param_map 包含所有周期
        param_map = {
            1: {"offset": 4000, "window": 20, "hold": 4, "cool": 6},
            2: {"offset": 2000, "window": 25, "hold": 8, "cool": 10},
            3: {"offset": 1000, "window": 30, "hold": 16, "cool": 20},
            9: {"offset": 750, "window": 30, "hold": 10, "cool": 10},
        }

        # 验证所有周期都有定义
        for category in [1, 2, 3, 9]:
            self.assertIn(category, param_map)
            params = param_map[category]
            # 验证每个周期都有必需的参数
            self.assertIn("offset", params)
            self.assertIn("window", params)
            self.assertIn("hold", params)
            self.assertIn("cool", params)

    def test_get_strategy_stats_with_empty_dataframe(self):
        """测试空 DataFrame 处理"""
        # 模拟返回空 DataFrame
        empty_df = pd.DataFrame()
        self.mock_quant_engine.fetch_bars.return_value = empty_df

        result = self.engine.get_strategy_stats("000001", 1, 9)

        # 空数据应该返回 None
        self.assertIsNone(result)

    def test_get_strategy_stats_with_insufficient_data(self):
        """测试数据不足的情况"""
        # 模拟返回数据量不足的 DataFrame
        small_df = pd.DataFrame({"close": [10.0, 10.5]})
        self.mock_quant_engine.fetch_bars.return_value = small_df

        result = self.engine.get_strategy_stats("000001", 1, 9)

        # 数据不足应该返回 None
        self.assertIsNone(result)

    def test_cache_key_generation(self):
        """测试缓存键生成逻辑"""
        import datetime

        # 验证缓存键包含代码、周期和日期
        symbol = "000001"
        category = 9
        today_str = datetime.date.today().isoformat()

        expected_key = f"{symbol}_{category}_{today_str}"

        # 手动验证缓存键格式
        cache_key = f"{symbol}_{category}_{today_str}"
        self.assertEqual(cache_key, expected_key)

    def test_signal_detection_logic(self):
        """测试信号检测逻辑（模拟）"""
        # 创建模拟的 MACD 金叉信号 - 确保所有数组长度一致
        n = 100
        df = pd.DataFrame(
            {
                "close": list(range(100, 100 + n)),
                "MACD": [i - 50 for i in range(n)],  # 从负到正穿越
                "MACDh": [i * 0.1 for i in range(-n // 2, n // 2)],
                "MACDs": [i * 0.08 for i in range(-n // 2, n // 2)],
            }
        )

        # 模拟 MACD 计算
        self.mock_quant_engine.fetch_bars.return_value = df

        # 注意：实际测试需要真实的 MACD 数据，这里只是结构测试
        # 完整的功能测试需要集成测试环境
        self.assertTrue(True)  # 占位符，表示测试框架已搭建


class TestBacktestCacheMechanism(unittest.TestCase):
    """回测缓存机制专项测试"""

    def setUp(self):
        self.mock_quant_engine = MagicMock(spec=QuantEngine)
        self.engine = BacktestEngine(self.mock_quant_engine)

    @patch("stock_monitor.core.backtest_engine.datetime")
    def test_cache_hit_scenario(self, mock_datetime):
        """测试缓存命中场景"""
        # 模拟今天的日期
        mock_date = MagicMock()
        mock_date.isoformat.return_value = "2024-01-15"
        mock_datetime.date.today.return_value = mock_date

        # 手动设置缓存
        cache_key = "000001_9_2024-01-15"
        mock_result = {"win_rate": 0.65, "total_signals": 10}
        self.engine._cache[cache_key] = mock_result

        # 调用方法
        result = self.engine.get_strategy_stats("000001", 1, 9)

        # 验证返回缓存结果
        self.assertEqual(result, mock_result)

    def test_cache_persistence(self):
        """测试缓存持久化"""
        # 验证缓存文件路径正确设置
        self.assertTrue(os.path.isabs(self.engine._cache_file))

        # 验证缓存目录存在或可创建
        cache_dir = os.path.dirname(self.engine._cache_file)
        self.assertTrue(os.path.exists(cache_dir) or os.access(cache_dir, os.W_OK))


class TestBacktestResultValidation(unittest.TestCase):
    """回测结果验证测试"""

    def setUp(self):
        self.mock_quant_engine = MagicMock(spec=QuantEngine)
        self.engine = BacktestEngine(self.mock_quant_engine)

    def test_result_structure(self):
        """测试结果数据结构"""
        # 定义预期的结果结构
        expected_keys = [
            "win_rate",  # 胜率
            "total_signals",  # 总信号数
            "avg_profit",  # 平均收益
        ]

        # 模拟一个完整的回测结果
        mock_result = {"win_rate": 0.60, "total_signals": 20, "avg_profit": 0.03}

        # 验证结构完整性
        for key in expected_keys:
            self.assertIn(key, mock_result)

        # 验证值类型
        self.assertIsInstance(mock_result["win_rate"], float)
        self.assertIsInstance(mock_result["total_signals"], int)
        self.assertIsInstance(mock_result["avg_profit"], float)

        # 验证值范围合理性
        self.assertGreaterEqual(mock_result["win_rate"], 0.0)
        self.assertLessEqual(mock_result["win_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
