"""
市场管理模块
负责处理市场相关的业务逻辑
"""

import datetime
from threading import Lock


class MarketSentiment:
    """市场情绪容器（涨跌家数、全市场成交等）"""

    def __init__(self):
        self.up_count = 0
        self.down_count = 0
        self.flat_count = 0
        self.total_count = 0
        self.last_update = None

    def update(self, up, down, flat, total):
        self.up_count = up
        self.down_count = down
        self.flat_count = flat
        self.total_count = total
        self.last_update = datetime.datetime.now()

    @property
    def up_ratio(self) -> float:
        """上涨家数占比"""
        if self.total_count == 0:
            return 0.5
        return self.up_count / self.total_count


class MarketManager:
    """市场管理器（单例）"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.sentiment = MarketSentiment()
        return cls._instance

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

    def update_sentiment(self, up, down, flat, total):
        """更新全市场情绪数据"""
        self.sentiment.update(up, down, flat, total)

    def get_sentiment(self) -> MarketSentiment:
        """获取当前情绪数据"""
        return self.sentiment

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
