import os
from pathlib import Path

# 构建配置文件
PROJECT_ROOT = Path(__file__).parent.absolute()

# PyInstaller 构建选项
BUILD_OPTIONS = {
    'windowed': True,           # 无控制台窗口
    'onefile': True,            # 打包成单个文件
    'icon': 'icon.ico',         # 图标文件
    'name': 'stock_monitor',    # 可执行文件名
}

# 需要添加的数据文件
DATA_FILES = [
    'stock_basic.json',
    'icon.png',
    'icon.ico'
]

# 必需的文件列表（用于构建前检查）
REQUIRED_FILES = [
    'main.py',
    'requirements.txt',
    'icon.ico',
    'icon.png',
    'stock_basic.json'
]

def get_build_command():
    """生成PyInstaller构建命令"""
    cmd = ['pyinstaller']
    
    # 添加构建选项
    if BUILD_OPTIONS['windowed']:
        cmd.append('--windowed')
    if BUILD_OPTIONS['onefile']:
        cmd.append('--onefile')
    if BUILD_OPTIONS['icon']:
        cmd.extend(['--icon', BUILD_OPTIONS['icon']])
    if BUILD_OPTIONS['name']:
        cmd.extend(['--name', BUILD_OPTIONS['name']])
    
    # 添加数据文件
    for data_file in DATA_FILES:
        cmd.extend(['--add-data', f'{data_file};.'])
    
    # 添加主程序
    cmd.append('main.py')
    
    return cmd