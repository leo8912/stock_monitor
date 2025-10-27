import os
import sys

def resource_path(relative_path):
    """获取资源文件路径，兼容PyInstaller打包和源码运行"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), relative_path)
    # 基于当前文件的目录定位resources文件夹
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resources_dir = os.path.join(current_dir, 'resources')
    return os.path.join(resources_dir, relative_path)

def get_stock_emoji(code, name):
    """根据股票代码和名称返回对应的emoji"""
    if code.startswith(('sh000', 'sz399', 'sz159', 'sh510')) or (name and ('指数' in name or '板块' in name)):
        return '📈'
    elif name and '银行' in name:
        return '🏦'
    elif name and '保险' in name:
        return '🛡️'
    elif name and '板块' in name:
        return '📊'
    elif name and ('能源' in name or '石油' in name or '煤' in name):
        return '⛽️'
    elif name and ('汽车' in name or '车' in name):
        return '🚗'
    elif name and ('科技' in name or '半导体' in name or '芯片' in name):
        return '💻'
    else:
        return '⭐️'

def is_equal(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) < tol
    except Exception:
        return False