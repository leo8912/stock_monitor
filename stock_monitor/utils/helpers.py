"""
工具函数模块
包含各种通用工具函数
"""

import os
import sys
from typing import Any, Callable


def resource_path(relative_path):
    """
    获取资源文件路径，兼容PyInstaller打包和源码运行

    Args:
        relative_path (str): 相对路径

    Returns:
        str: 资源文件的绝对路径
    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller打包环境
        base_path = sys._MEIPASS
        # 特殊处理zhconv资源文件
        if relative_path == "zhcdict.json":
            return os.path.join(base_path, "zhconv", relative_path)
        return os.path.join(base_path, "stock_monitor", "resources", relative_path)
    # 源码运行环境
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 特殊处理zhconv资源文件
    if relative_path == "zhcdict.json":
        try:
            import pkg_resources

            return pkg_resources.resource_filename("zhconv", "zhcdict.json")
        except Exception:
            # Fallback方法
            import zhconv

            zhconv_path = os.path.dirname(zhconv.__file__)
            return os.path.join(zhconv_path, relative_path)
    resources_dir = os.path.join(current_dir, "resources")
    return os.path.join(resources_dir, relative_path)


def get_config_manager():
    """
    获取配置管理器实例

    Returns:
        ConfigManager: 配置管理器实例
    """
    from stock_monitor.config.manager import ConfigManager

    return ConfigManager()


def get_stock_emoji(code, name):
    """
    根据股票代码和名称返回对应的emoji

    Args:
        code (str): 股票代码
        name (str): 股票名称

    Returns:
        str: 对应的emoji字符
    """
    if code.startswith(("sh000", "sz399", "sz159", "sh510")) or (
        name and ("指数" in name or "板块" in name)
    ):
        return "📈"
    elif code.startswith("hk"):
        return "🇭🇰"
    elif name and "银行" in name:
        return "🏦"
    elif name and "保险" in name:
        return "🛡️"
    elif name and "板块" in name:
        return "📊"
    elif name and ("能源" in name or "石油" in name or "煤" in name):
        return "⛽️"
    elif name and ("汽车" in name or "车" in name):
        return "🚗"
    elif name and ("科技" in name or "半导体" in name or "芯片" in name):
        return "💻"
    else:
        return "⭐️"


def is_equal(a, b, tol=0.01):
    """
    比较两个字符串数值是否近似相等

    Args:
        a: 第一个数值字符串
        b: 第二个数值字符串
        tol (float): 容差值，默认为0.01

    Returns:
        bool: 如果两个数值差的绝对值小于容差值则返回True，否则返回False
    """
    try:
        return abs(float(a) - float(b)) < tol
    except Exception:
        return False


def handle_exception(
    operation_name: str,
    operation_func: Callable[[], Any],
    default_return: Any,
    logger: Any,
) -> Any:
    """
    通用异常处理函数

    Args:
        operation_name: 操作名称
        operation_func: 执行操作的函数
        default_return: 默认返回值
        logger: 日志记录器

    Returns:
        操作结果或默认值
    """
    try:
        return operation_func()
    except Exception as e:
        error_msg = f"{operation_name}时发生错误：{e}"
        logger.error(error_msg)
        return default_return


def _safe_bool_conversion(value, default=False):
    """安全地将值转换为布尔值（从 settings_dialog.py 迁移）"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return default


def _safe_int_conversion(value, default=0):
    """安全地将值转换为整数（从 settings_dialog.py 迁移）"""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default
