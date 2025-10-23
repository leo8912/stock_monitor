import unittest
import sys
import os
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.utils.helpers import resource_path

class TestUtils(unittest.TestCase):
    
    def test_resource_path_pyinstaller(self):
        """测试PyInstaller环境下的资源路径"""
        # 模拟PyInstaller环境
        with patch.object(sys, '_MEIPASS', '/tmp/_MEI', create=True):
            path = resource_path('test.txt')
            # 使用 normpath 来处理路径分隔符
            self.assertEqual(os.path.normpath(path), os.path.normpath('/tmp/_MEI/test.txt'))
    
    def test_resource_path_normal(self):
        """测试普通环境下的资源路径"""
        # 确保_MEIPASS属性不存在
        if hasattr(sys, '_MEIPASS'):
            delattr(sys, '_MEIPASS')
            
        path = resource_path('test.txt')
        # 应该返回当前目录下的相对路径
        expected = os.path.join(os.path.abspath("."), 'test.txt')
        self.assertEqual(path, expected)

if __name__ == '__main__':
    unittest.main()