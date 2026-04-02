"""
配置读取辅助工具模块
提取重复的配置读取逻辑，提供统一的访问接口
"""

from typing import Any, Optional


class ConfigHelper:
    """配置读取辅助类"""

    def __init__(self, config_manager):
        """
        初始化配置助手

        Args:
            config_manager: ConfigManager 实例
        """
        self.config_manager = config_manager

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            配置值或默认值
        """
        return self.config_manager.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
        """
        self.config_manager.set(key, value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        安全地获取布尔值配置

        Args:
            key: 配置键
            default: 默认布尔值

        Returns:
            布尔值
        """
        value = self.config_manager.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(default)

    def get_int(self, key: str, default: int = 0) -> int:
        """
        安全地获取整数配置

        Args:
            key: 配置键
            default: 默认整数值

        Returns:
            整数值
        """
        value = self.config_manager.get(key, default)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
        return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """
        安全地获取浮点数配置

        Args:
            key: 配置键
            default: 默认浮数值

        Returns:
            浮数值
        """
        value = self.config_manager.get(key, default)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
        return default

    def get_list(self, key: str, default: Optional[list] = None) -> list:
        """
        安全地获取列表配置

        Args:
            key: 配置键
            default: 默认列表

        Returns:
            列表值
        """
        if default is None:
            default = []
        value = self.config_manager.get(key, default)
        if isinstance(value, list):
            return value
        return default

    def get_str(self, key: str, default: str = "") -> str:
        """
        安全地获取字符串配置

        Args:
            key: 配置键
            default: 默认字符串

        Returns:
            字符串值
        """
        value = self.config_manager.get(key, default)
        if isinstance(value, str):
            return value
        return str(default)


def safe_get_config(config_manager, key: str, default: Any = None) -> Any:
    """
    便捷函数：安全地获取配置值

    Args:
        config_manager: ConfigManager 实例
        key: 配置键
        default: 默认值

    Returns:
        配置值或默认值

    Example:
        >>> stocks = safe_get_config(config_manager, "user_stocks", [])
        >>> enabled = safe_get_config(config_manager, "quant_enabled", False)
    """
    return config_manager.get(key, default)


def safe_get_bool(config_manager, key: str, default: bool = False) -> bool:
    """
    便捷函数：安全地将配置转换为布尔值

    Args:
        config_manager: ConfigManager 实例
        key: 配置键
        default: 默认布尔值

    Returns:
        布尔值
    """
    value = config_manager.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(default)


def safe_get_int(config_manager, key: str, default: int = 0) -> int:
    """
    便捷函数：安全地将配置转换为整数

    Args:
        config_manager: ConfigManager 实例
        key: 配置键
        default: 默认整数值

    Returns:
        整数值
    """
    value = config_manager.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default


# 预定义常用配置键常量
class ConfigKeys:
    """配置键常量定义，避免硬编码字符串"""

    # 用户自选股
    USER_STOCKS = "user_stocks"

    # 刷新间隔
    REFRESH_INTERVAL = "refresh_interval"

    # 量化相关
    QUANT_ENABLED = "quant_enabled"
    QUANT_SCAN_INTERVAL = "quant_scan_interval"
    MACD_THRESHOLD = "macd_threshold"
    RSRS_THRESHOLD = "rsrs_threshold"

    # 显示相关
    FONT_FAMILY = "font_family"
    FONT_SIZE = "font_size"
    WINDOW_TRANSPARENCY = "window_transparency"
    TRANSPARENCY = "transparency"

    # 消息推送
    WECOM_WEBHOOK = "wecom_webhook"
    PUSH_MODE = "push_mode"

    # 窗口位置
    WINDOW_POS = "window_pos"

    # 基本面筛选
    FILTER_PE = "filter_pe"
    FILTER_ROE = "filter_roe"
    FILTER_MARKET_CAP = "filter_market_cap"
