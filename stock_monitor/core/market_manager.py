"""
市场管理模块
负责处理市场相关的业务逻辑
"""

import datetime


class MarketManager:
    """市场管理器"""

    @staticmethod
    def is_market_open() -> bool:
        """
        检查A股是否开市

        Returns:
            bool: 是否开市
        """
        now = datetime.datetime.now()
        if now.weekday() >= 5:  # 周末
            return False
        t = now.time()
        return (datetime.time(9, 15) <= t <= datetime.time(11, 30)) or (
            datetime.time(13, 0) <= t <= datetime.time(15, 0)
        )

    @staticmethod
    def get_market_status() -> str:
        """
        获取市场状态描述

        Returns:
            str: 市场状态描述
        """
        if MarketManager.is_market_open():
            return "开市"
        else:
            return "闭市"

    @staticmethod
    def get_refresh_interval(base_interval: int) -> int:
        """
        根据市场状态获取刷新间隔

        Args:
            base_interval (int): 基础刷新间隔（秒）

        Returns:
            int: 实际刷新间隔（秒）
        """
        if MarketManager.is_market_open():
            return base_interval
        else:
            return 30  # 闭市期间固定30秒刷新一次


# 创建全局市场管理器实例
market_manager = MarketManager()
