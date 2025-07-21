#!/usr/bin/env python3
"""
测试构建脚本 - 验证构建过程
"""

import os
import sys
import subprocess
from pathlib import Path

def test_dependencies():
    """测试依赖是否安装"""
    print("测试依赖安装...")
    
    try:
        import PyQt5
        print("✓ PyQt5 已安装")
    except ImportError:
        print("✗ PyQt5 未安装")
        return False
        
    try:
        import easyquotation
        print("✓ easyquotation 已安装")
    except ImportError:
        print("✗ easyquotation 未安装")
        return False
        
    try:
        import win32com
        print("✓ pywin32 已安装")
    except ImportError:
        print("✗ pywin32 未安装")
        return False
        
    return True

def test_files():
    """测试必要文件是否存在"""
    print("\n测试必要文件...")
    
    required_files = [
        'main.py',
        'requirements.txt', 
        'icon.ico',
        'icon.png',
        'stock_basic.json',
        'theme_config.json'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file} 存在")
        else:
            print(f"✗ {file} 缺失")
            return False
            
    return True

def test_pyinstaller():
    """测试PyInstaller是否可用"""
    print("\n测试PyInstaller...")
    
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ PyInstaller 可用: {result.stdout.strip()}")
            return True
        else:
            print("✗ PyInstaller 不可用")
            return False
    except FileNotFoundError:
        print("✗ PyInstaller 未安装")
        return False

def test_build_script():
    """测试构建脚本"""
    print("\n测试构建脚本...")
    
    if not os.path.exists('build.py'):
        print("✗ build.py 不存在")
        return False
        
    print("✓ build.py 存在")
    return True

def main():
    """主测试函数"""
    print("=== 构建环境测试 ===")
    print("本脚本用于测试GitHub Actions构建环境")
    print()
    
    tests = [
        ("依赖测试", test_dependencies),
        ("文件测试", test_files),
        ("PyInstaller测试", test_pyinstaller),
        ("构建脚本测试", test_build_script)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
            print(f"✓ {test_name} 通过")
        else:
            print(f"✗ {test_name} 失败")
    
    print(f"\n=== 测试结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("🎉 所有测试通过！构建环境正常")
        print("\n可以运行以下命令进行构建:")
        print("python build.py")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查环境配置")
        sys.exit(1)

if __name__ == '__main__':
    main() 