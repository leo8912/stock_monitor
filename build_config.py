import os
from pathlib import Path

# 构建配置文件
PROJECT_ROOT = Path(__file__).parent.absolute()

# PyInstaller 构建选项
BUILD_OPTIONS = {
    'windowed': True,           # 无控制台窗口
    'onefile': True,            # 打包成单个文件
    'icon': 'stock_monitor/resources/icon.ico',  # 图标文件
    'name': 'stock_monitor',    # 可执行文件名
}

# 需要添加的数据文件
DATA_FILES = [
    'stock_monitor/resources/stock_basic.json',
    'stock_monitor/resources/icon.ico',
    ('zhconv/zhcdict.json', 'zhconv')
]

# 必需的文件列表（用于构建前检查）
REQUIRED_FILES = [
    'stock_monitor/main.py',
    'requirements.txt',
    'stock_monitor/resources/icon.ico',
    'stock_monitor/resources/stock_basic.json'
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
        if isinstance(data_file, tuple):
            # 处理元组形式的文件路径 (source, dest)
            src, dest = data_file
            cmd.extend(['--add-data', f'{src};{dest}'])
        else:
            # 处理字符串形式的文件路径
            cmd.extend(['--add-data', f'{data_file};stock_monitor/resources'])
    
    # 添加主程序
    cmd.append('stock_monitor/main.py')
    
    return cmd