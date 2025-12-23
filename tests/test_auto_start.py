#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开机启动功能测试脚本
"""

import os
import sys
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from stock_monitor.config.manager import ConfigManager
from stock_monitor.core.startup import setup_auto_start


def test_auto_start():
    """测试开机启动功能"""
    print("=== 开机启动功能测试 ===\n")
    
    # 获取启动文件夹路径
    startup_folder = os.path.join(
        os.environ.get('APPDATA', ''),
        'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
    )
    
    shortcut_path = os.path.join(startup_folder, 'StockMonitor.lnk')
    
    print(f"启动文件夹路径: {startup_folder}")
    print(f"快捷方式路径: {shortcut_path}")
    
    # 检查启动文件夹是否存在
    if not os.path.exists(startup_folder):
        print("错误: 启动文件夹不存在!")
        return False
        
    print(f"启动文件夹存在: {os.path.exists(startup_folder)}")
    
    # 检查快捷方式是否存在
    shortcut_exists = os.path.exists(shortcut_path)
    print(f"快捷方式存在: {shortcut_exists}")
    
    # 获取当前配置
    config_manager = ConfigManager()
    auto_start_config = config_manager.get("auto_start", False)
    print(f"配置中的开机启动设置: {auto_start_config}")
    
    # 测试开启开机启动
    print("\n--- 测试开启开机启动 ---")
    config_manager.set("auto_start", True)
    setup_auto_start()
    
    # 检查快捷方式是否创建
    shortcut_exists_after_enable = os.path.exists(shortcut_path)
    print(f"开启后快捷方式存在: {shortcut_exists_after_enable}")
    
    # 测试关闭开机启动
    print("\n--- 测试关闭开机启动 ---")
    config_manager.set("auto_start", False)
    setup_auto_start()
    
    # 检查快捷方式是否删除
    shortcut_exists_after_disable = os.path.exists(shortcut_path)
    print(f"关闭后快捷方式存在: {shortcut_exists_after_disable}")
    
    # 恢复原始配置
    config_manager.set("auto_start", auto_start_config)
    setup_auto_start()
    
    print(f"\n已恢复原始配置: {auto_start_config}")
    
    # 最终检查
    final_shortcut_exists = os.path.exists(shortcut_path)
    print(f"最终快捷方式状态: {final_shortcut_exists}")
    
    print("\n=== 测试完成 ===")
    return True


if __name__ == '__main__':
    test_auto_start()