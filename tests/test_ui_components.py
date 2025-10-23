import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.ui.components import get_stock_emoji

class TestUIComponents(unittest.TestCase):
    
    def test_get_stock_emoji_index(self):
        """测试指数类股票emoji"""
        self.assertEqual(get_stock_emoji('sh000001', '上证指数'), '📈')
        self.assertEqual(get_stock_emoji('sz399001', '深证成指'), '📈')
    
    def test_get_stock_emoji_bank(self):
        """测试银行类股票emoji"""
        self.assertEqual(get_stock_emoji('sh600000', '浦发银行'), '🏦')
        self.assertEqual(get_stock_emoji('sz000001', '平安银行'), '🏦')
    
    def test_get_stock_emoji_insurance(self):
        """测试保险类股票emoji"""
        self.assertEqual(get_stock_emoji('sh601318', '中国保险'), '🛡️')
    
    def test_get_stock_emoji_energy(self):
        """测试能源类股票emoji"""
        self.assertEqual(get_stock_emoji('sh600028', '中国石油'), '⛽️')
        self.assertEqual(get_stock_emoji('sh601857', '中国石油'), '⛽️')
    
    def test_get_stock_emoji_car(self):
        """测试汽车类股票emoji"""
        self.assertEqual(get_stock_emoji('sh600104', '上汽汽车'), '🚗')
    
    def test_get_stock_emoji_tech(self):
        """测试科技类股票emoji"""
        self.assertEqual(get_stock_emoji('sz300032', '金龙科技'), '💻')
        self.assertEqual(get_stock_emoji('sh600460', '士兰微半导体'), '💻')
    
    def test_get_stock_emoji_default(self):
        """测试默认股票emoji"""
        self.assertEqual(get_stock_emoji('sh600001', '未知股票'), '⭐️')

if __name__ == '__main__':
    unittest.main()