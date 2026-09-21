import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stock_monitor.utils.helpers import get_stock_emoji, is_equal, safe_float
from stock_monitor.utils.stock_utils import StockCodeProcessor


class TestSafeFloat(unittest.TestCase):
    """safe_float 统一容错转换（数据源解析 / 报表导出共享）"""

    def test_valid_values(self):
        self.assertEqual(safe_float("1.23"), 1.23)
        self.assertEqual(safe_float(5), 5.0)
        self.assertEqual(safe_float(-0.5), -0.5)

    def test_invalid_returns_default(self):
        self.assertEqual(safe_float(None), 0.0)
        self.assertEqual(safe_float("abc"), 0.0)
        self.assertEqual(safe_float(""), 0.0)
        self.assertEqual(safe_float([], default=1.5), 1.5)

    def test_custom_default_with_none(self):
        self.assertEqual(safe_float(None, default=8.8), 8.8)


class TestHelpers(unittest.TestCase):
    def test_is_equal(self):
        """测试数值近似相等判断函数"""
        self.assertTrue(is_equal("1.00", "1.00"))
        self.assertTrue(is_equal("1.00", "1.01", 0.02))
        self.assertFalse(is_equal("1.00", "1.05", 0.02))
        self.assertTrue(is_equal("0.00", "0.00"))
        self.assertFalse(is_equal("abc", "1.00"))

    def test_format_stock_code(self):
        """测试股票代码格式化函数"""
        processor = StockCodeProcessor()
        # 测试6位数字代码
        self.assertEqual(processor.format_stock_code("600460"), "sh600460")
        # 修改000001的期望结果为空，因为我们不再自动为它添加前缀
        self.assertEqual(processor.format_stock_code("000001"), "000001")
        self.assertEqual(processor.format_stock_code("300001"), "sz300001")
        self.assertEqual(processor.format_stock_code("510050"), "sh510050")

        # 测试已格式化代码
        self.assertEqual(processor.format_stock_code("sh600460"), "sh600460")
        self.assertEqual(processor.format_stock_code("sz000001"), "sz000001")

        # 测试无效代码
        self.assertEqual(processor.format_stock_code("invalid"), "invalid")
        self.assertEqual(
            processor.format_stock_code("12345"), "12345"
        )  # 5位数字代码保持不变
        self.assertIsNone(processor.format_stock_code(""))

    def test_get_stock_emoji(self):
        """测试获取股票emoji函数"""
        # 测试指数
        self.assertEqual(get_stock_emoji("sh000001", "上证指数"), "📈")
        self.assertEqual(get_stock_emoji("sz399001", "深证成指"), "📈")

        # 测试港股
        self.assertEqual(get_stock_emoji("hk00700", "腾讯控股"), "🇭🇰")

        # 测试银行股
        self.assertEqual(get_stock_emoji("sh600036", "招商银行"), "🏦")

        # 测试保险股
        # 注意：当前实现中没有针对保险股的特殊处理，所以返回默认emoji
        self.assertEqual(get_stock_emoji("sh601318", "中国平安"), "⭐️")

        # 测试普通股
        self.assertEqual(get_stock_emoji("sh600460", "士兰微"), "⭐️")


if __name__ == "__main__":
    unittest.main()
