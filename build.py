#!/usr/bin/env python3
"""
构建脚本 - 用于GitHub Actions自动构建
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def install_easyquotation():
    """安装easyquotation并处理依赖"""
    try:
        import easyquotation
        print("✓ easyquotation已安装")
        
        # 获取easyquotation安装路径
        import easyquotation
        eq_path = os.path.dirname(easyquotation.__file__)
        stock_codes_path = os.path.join(eq_path, 'stock_codes.conf')
        
        # 如果stock_codes.conf不存在，创建一个空的
        if not os.path.exists(stock_codes_path):
            with open(stock_codes_path, 'w', encoding='utf-8') as f:
                f.write("# Stock codes configuration\n")
            print(f"✓ 创建stock_codes.conf: {stock_codes_path}")
            
        return eq_path
    except ImportError:
        print("✗ easyquotation未安装，正在安装...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'easyquotation'])
        return install_easyquotation()

def build_executable():
    """构建可执行文件"""
    print("开始构建可执行文件...")
    
    # 安装依赖
    eq_path = install_easyquotation()
    
    # 构建命令
    cmd = [
        'pyinstaller',
        '--windowed',  # 无控制台窗口
        '--onefile',   # 打包成单个文件
        '--icon=icon.ico',
        '--name=stock_monitor',
        f'--add-data={eq_path}/stock_codes.conf;easyquotation',
        '--add-data=stock_basic.json;.',
        '--add-data=theme_config.json;.',
        '--add-data=icon.png;.',
        '--add-data=icon.ico;.',
        'main.py'
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("✓ 构建成功！")
        
        # 检查输出文件
        exe_path = Path('dist/stock_monitor.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"✓ 可执行文件大小: {size_mb:.1f} MB")
            return True
        else:
            print("✗ 可执行文件未生成")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"✗ 构建失败: {e}")
        return False

def main():
    """主函数"""
    print("=== A股行情监控软件构建脚本 ===")
    print("本脚本用于GitHub Actions自动构建")
    print()
    
    # 检查必要文件
    required_files = ['main.py', 'requirements.txt', 'icon.ico', 'icon.png']
    for file in required_files:
        if not os.path.exists(file):
            print(f"✗ 缺少必要文件: {file}")
            sys.exit(1)
        print(f"✓ 找到文件: {file}")
    
    print()
    
    # 构建可执行文件
    if build_executable():
        print("\n🎉 构建完成！")
        print("可执行文件位置: dist/stock_monitor.exe")
        sys.exit(0)
    else:
        print("\n❌ 构建失败！")
        sys.exit(1)

if __name__ == '__main__':
    main() 