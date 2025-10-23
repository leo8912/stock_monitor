import unittest
import sys
import os
import json
import tempfile
import shutil
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from stock_monitor.config.manager import load_config, save_config

class TestConfig(unittest.TestCase):
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        self.original_config_path = os.path.join(
            os.path.dirname(__file__), '..', 'stock_monitor', 'config.json')
        
    def tearDown(self):
        """测试后清理"""
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        # 清理可能创建的config.json文件
        test_config_path = os.path.join(
            os.path.dirname(__file__), '..', 'config.json')
        if os.path.exists(test_config_path):
            os.remove(test_config_path)
    
    def test_load_config_creates_default(self):
        """测试加载配置时创建默认配置"""
        # 保存原始CONFIG_PATH
        from stock_monitor.config.manager import CONFIG_PATH
        original_config_path = CONFIG_PATH
        
        # 设置测试路径
        test_config_path = os.path.join(self.test_dir, 'config.json')
        
        # 使用patch来修改CONFIG_PATH
        with patch('stock_monitor.config.manager.CONFIG_PATH', test_config_path):
            # 确保文件不存在
            if os.path.exists(test_config_path):
                os.remove(test_config_path)
                
            # 加载配置应该创建默认配置
            config = load_config()
            
            # 检查默认配置内容
            self.assertIn('user_stocks', config)
            self.assertIn('refresh_interval', config)
            self.assertIn('github_token', config)
            self.assertEqual(config['refresh_interval'], 5)
            self.assertEqual(len(config['user_stocks']), 4)
            
            # 检查文件是否已创建
            self.assertTrue(os.path.exists(test_config_path))
            
            # 检查文件内容
            with open(test_config_path, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            self.assertEqual(config, saved_config)
    
    def test_save_config(self):
        """测试保存配置"""
        # 保存原始CONFIG_PATH
        from stock_monitor.config.manager import CONFIG_PATH
        original_config_path = CONFIG_PATH
        
        # 设置测试路径
        test_config_path = os.path.join(self.test_dir, 'config.json')
        
        # 使用patch来修改CONFIG_PATH
        with patch('stock_monitor.config.manager.CONFIG_PATH', test_config_path):
            # 创建测试配置
            test_config = {
                'user_stocks': ['sh600460'],
                'refresh_interval': 10,
                'github_token': 'test_token'
            }
            
            # 保存配置
            save_config(test_config)
            
            # 检查文件是否已创建并包含正确内容
            self.assertTrue(os.path.exists(test_config_path))
            with open(test_config_path, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            self.assertEqual(test_config, saved_config)
            
    def test_load_config_json_decode_error(self):
        """测试JSON解码错误处理"""
        from stock_monitor.config.manager import CONFIG_PATH
        
        # 设置测试路径
        test_config_path = os.path.join(self.test_dir, 'config.json')
        
        # 使用patch来修改CONFIG_PATH
        with patch('stock_monitor.config.manager.CONFIG_PATH', test_config_path):
            # 创建一个无效的JSON文件
            with open(test_config_path, 'w', encoding='utf-8') as f:
                f.write('invalid json content')
                
            # 加载配置应该处理JSON解码错误并创建默认配置
            config = load_config()
            
            # 检查是否返回了默认配置
            self.assertIn('user_stocks', config)
            self.assertIn('refresh_interval', config)
            
            # 检查备份文件是否已创建
            backup_path = test_config_path + ".bak"
            self.assertTrue(os.path.exists(backup_path))
            
    def test_load_config_permission_error(self):
        """测试权限错误处理"""
        from unittest.mock import mock_open, patch
        from stock_monitor.config.manager import CONFIG_PATH
        
        # 设置测试路径
        test_config_path = os.path.join(self.test_dir, 'config.json')
        
        # 创建一个空文件
        with open(test_config_path, 'w') as f:
            pass
            
        # 使用patch模拟权限错误
        with patch('stock_monitor.config.manager.CONFIG_PATH', test_config_path):
            with patch('builtins.open', mock_open()) as mock_file:
                mock_file.side_effect = PermissionError("Permission denied")
                
                # 加载配置应该处理权限错误
                config = load_config()
                
                # 检查是否返回了默认配置
                self.assertIn('user_stocks', config)
                self.assertIn('refresh_interval', config)
                self.assertEqual(config['refresh_interval'], 5)

if __name__ == '__main__':
    unittest.main()