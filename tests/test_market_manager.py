import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.core.market_manager import MarketManager

class TestMarketManager(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        self.market_manager = MarketManager()
        
    def test_initialization(self):
        """测试市场管理器初始化"""
        self.assertIsInstance(self.market_manager, MarketManager)
        self.assertIsNone(self.market_manager.last_update_time)
        
    def test_update_database_on_startup(self):
        """测试启动时数据库更新方法"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.market_manager, 'update_database_on_startup'))
        # 注意：实际测试需要mock网络请求和文件操作
        
    def test_start_database_update_scheduler(self):
        """测试启动数据库更新调度器"""
        # 确保方法存在且可调用
        self.assertTrue(hasattr(self.market_manager, 'start_database_update_scheduler'))
        # 注意：实际测试需要mock线程和定时器

if __name__ == '__main__':
    unittest.main()