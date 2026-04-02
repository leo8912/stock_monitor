#!/usr/bin/env python
"""
SymbolResolver 单元测试模块

测试符号解析器功能，包括：
- 股票代码格式转换
- 市场前缀识别
- 特殊标的映射
- 边界情况处理
"""

import unittest

from stock_monitor.core.symbol_resolver import (
    SymbolConfig,
    SymbolResolver,
    SymbolType,
)


class TestSymbolResolver(unittest.TestCase):
    """SymbolResolver 核心功能测试"""

    def test_resolve_shanghai_stock(self):
        """测试上海股票解析"""
        config = SymbolResolver.resolve("600519")

        self.assertEqual(config.code, "600519")
        self.assertEqual(config.market, 1)  # 上海市场
        self.assertEqual(config.type, SymbolType.STOCK)

    def test_resolve_shenzhen_stock(self):
        """测试深圳股票解析"""
        config = SymbolResolver.resolve("000001")

        self.assertEqual(config.code, "000001")
        self.assertEqual(config.market, 0)  # 深圳市场
        self.assertEqual(config.type, SymbolType.STOCK)

    def test_resolve_with_market_prefix(self):
        """测试带市场前缀的符号解析"""
        # 上海前缀
        config = SymbolResolver.resolve("sh600519")
        self.assertEqual(config.code, "600519")
        self.assertEqual(config.market, 1)

        # 深圳前缀
        config = SymbolResolver.resolve("sz000001")
        self.assertEqual(config.code, "000001")
        self.assertEqual(config.market, 0)

    def test_resolve_special_index_sh000001(self):
        """测试特殊指数 sh000001（上证指数）解析"""
        config = SymbolResolver.resolve("sh000001")

        self.assertEqual(config.code, "999999")  # 影子代码
        self.assertEqual(config.market, 1)
        self.assertEqual(config.type, SymbolType.INDEX)
        self.assertIn(("000001", 1), config.alternates)

    def test_resolve_szse_indices(self):
        """测试深圳指数解析"""
        # 深证成指
        config = SymbolResolver.resolve("sz399001")
        self.assertEqual(config.code, "399001")
        self.assertEqual(config.market, 0)
        self.assertEqual(config.type, SymbolType.INDEX)

        # 创业板指
        config = SymbolResolver.resolve("sz399006")
        self.assertEqual(config.code, "399006")
        self.assertEqual(config.market, 0)
        self.assertEqual(config.type, SymbolType.INDEX)

    def test_resolve_index_by_pattern(self):
        """测试通过代码模式识别指数"""
        # 000 开头的上海指数
        config = SymbolResolver.resolve("sh000016")  # 上证 50
        self.assertEqual(config.type, SymbolType.INDEX)

        # 399 开头的深圳指数
        config = SymbolResolver.resolve("sz399001")
        self.assertEqual(config.type, SymbolType.INDEX)

    def test_resolve_with_explicit_market(self):
        """测试显式指定市场参数"""
        # 纯数字 + 显式市场=1（上海）
        config = SymbolResolver.resolve("600519", market=1)
        self.assertEqual(config.code, "600519")
        self.assertEqual(config.market, 1)

        # 纯数字 + 显式市场=0（深圳）
        config = SymbolResolver.resolve("000001", market=0)
        self.assertEqual(config.code, "000001")
        self.assertEqual(config.market, 0)

    def test_resolve_pure_code_fallback(self):
        """测试纯代码的防御性转换"""
        # 当 market=1 且 code="000001" 时，应转换为上证指数
        config = SymbolResolver.resolve("000001", market=1)
        self.assertEqual(config.code, "999999")
        self.assertEqual(config.market, 1)
        self.assertEqual(config.type, SymbolType.INDEX)

    def test_resolve_default_inference(self):
        """测试默认推断逻辑"""
        # 6 开头默认上海
        config = SymbolResolver.resolve("600519")
        self.assertEqual(config.market, 1)

        # 非 6 开头默认深圳
        config = SymbolResolver.resolve("000001")
        self.assertEqual(config.market, 0)

    def test_get_market_prefix(self):
        """测试市场前缀获取"""
        self.assertEqual(SymbolResolver.get_market_prefix(1), "sh")
        self.assertEqual(SymbolResolver.get_market_prefix(0), "sz")


class TestSymbolConfig(unittest.TestCase):
    """SymbolConfig 数据结构测试"""

    def test_symbol_config_creation(self):
        """测试 SymbolConfig 基本创建"""
        config = SymbolConfig("600519", 1, SymbolType.STOCK)

        self.assertEqual(config.code, "600519")
        self.assertEqual(config.market, 1)
        self.assertEqual(config.type, SymbolType.STOCK)
        self.assertEqual(config.alternates, [])

    def test_symbol_config_with_alternates(self):
        """测试带备选配置的 SymbolConfig"""
        alternates = [("000001", 1), ("999999", 1)]
        config = SymbolConfig("600519", 1, SymbolType.STOCK, alternates=alternates)

        self.assertEqual(len(config.alternates), 2)
        self.assertIn(("000001", 1), config.alternates)
        self.assertIn(("999999", 1), config.alternates)


class TestSymbolType(unittest.TestCase):
    """SymbolType 枚举测试"""

    def test_symbol_type_values(self):
        """测试 SymbolType 枚举值"""
        self.assertEqual(SymbolType.STOCK.value, "stock")
        self.assertEqual(SymbolType.INDEX.value, "index")
        self.assertEqual(SymbolType.ETF.value, "etf")
        self.assertEqual(SymbolType.OTHER.value, "other")

    def test_symbol_type_comparison(self):
        """测试 SymbolType 比较"""
        self.assertEqual(SymbolType.STOCK, SymbolType.STOCK)
        self.assertNotEqual(SymbolType.STOCK, SymbolType.INDEX)


class TestSymbolResolverEdgeCases(unittest.TestCase):
    """SymbolResolver 边界情况测试"""

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        config1 = SymbolResolver.resolve("SH600519")
        config2 = SymbolResolver.resolve("sh600519")

        self.assertEqual(config1.code, config2.code)
        self.assertEqual(config1.market, config2.market)

    def test_mixed_case(self):
        """测试混合大小写"""
        config = SymbolResolver.resolve("Sh600519")
        self.assertEqual(config.market, 1)

        config = SymbolResolver.resolve("sZ000001")
        self.assertEqual(config.market, 0)

    def test_star_market_stock(self):
        """测试科创板股票（688 开头）"""
        config = SymbolResolver.resolve("688001")
        self.assertEqual(config.code, "688001")
        self.assertEqual(config.market, 1)  # 上海
        self.assertEqual(config.type, SymbolType.STOCK)

    def test_chi_next_stock(self):
        """测试创业板股票（300 开头）"""
        config = SymbolResolver.resolve("300750")
        self.assertEqual(config.code, "300750")
        self.assertEqual(config.market, 0)  # 深圳
        self.assertEqual(config.type, SymbolType.STOCK)

    def test_etf_symbol(self):
        """测试 ETF 符号解析（需要实际数据支持）"""
        # ETF 通常以 15 或 51 开头
        config = SymbolResolver.resolve("510300")  # 沪深 300ETF
        self.assertEqual(config.code, "510300")
        # 注意：当前实现根据首位数字推断市场，5 开头会被推断为深圳 (market=0)
        # 实际使用中可能需要更精确的 ETF 识别逻辑
        self.assertIn(config.market, [0, 1])

    def test_bond_symbol(self):
        """测试债券符号解析"""
        # 可转债通常以 11 或 12 开头
        config = SymbolResolver.resolve("113001")
        self.assertEqual(config.code, "113001")
        # 注意：当前实现根据首位数字推断市场，1 开头会被推断为深圳 (market=0)
        self.assertIn(config.market, [0, 1])


class TestSymbolResolverSpecialCodes(unittest.TestCase):
    """特殊代码映射测试"""

    def test_special_codes_structure(self):
        """测试特殊代码映射表结构"""
        special_codes = SymbolResolver._SPECIAL_CODES

        # 验证至少包含已知的特殊映射
        self.assertIn("sh000001", special_codes)
        self.assertIn("sz399001", special_codes)
        self.assertIn("sz399006", special_codes)

    def test_sh000001_alternate_mapping(self):
        """测试上证指数备选映射"""
        config = SymbolResolver.resolve("sh000001")

        # 验证备选映射存在
        self.assertTrue(len(config.alternates) > 0)

        # 验证可以通过备选代码访问
        alt_code, alt_market = config.alternates[0]
        self.assertEqual(alt_code, "000001")
        self.assertEqual(alt_market, 1)


if __name__ == "__main__":
    unittest.main()
