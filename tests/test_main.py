import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestMain(unittest.TestCase):
    """测试主程序入口"""

    def test_import_main(self):
        """测试能否成功导入主模块"""
        try:
            from stock_monitor import main
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"导入主模块失败: {e}")

if __name__ == '__main__':
    unittest.main()