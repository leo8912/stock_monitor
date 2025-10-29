import os
import sys
from typing import Callable, Any, Optional

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

def format_stock_code(code):
    """
    格式化股票代码，确保正确的前缀
    
    Args:
        code: 股票代码字符串
        
    Returns:
        格式化后的股票代码，如果无效则返回None
    """
    if not isinstance(code, str) or not code:
        return None
        
    code = code.strip().lower()
    
    # 移除可能存在的额外字符
    code = ''.join(c for c in code if c.isalnum())
    
    if not code:
        return None
        
    # 检查是否已经有正确前缀
    if code.startswith('sh') or code.startswith('sz'):
        # 验证代码长度和数字部分
        if len(code) == 8 and code[2:].isdigit():
            return code
        else:
            return None
            
    # 6位纯数字代码
    elif len(code) == 6 and code.isdigit():
        if code.startswith('6') or code.startswith('5'):
            return 'sh' + code
        elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
            return 'sz' + code
        else:
            return None
    
    # 其他情况返回None
    return None