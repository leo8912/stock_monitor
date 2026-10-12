"""
市场管理模块
负责处理市场相关的业务逻辑
"""

import datetime
from threading import Lock

# 法定节假日休市日集合（格式 "YYYY-MM-DD"）。项目内无第三方交易日历数据源，
# 当前为空集（行为与仅判周末一致）；填入具体日期后 is_market_open 会一并排除。
_HOLIDAYS: frozenset[str] = frozenset()


class MarketSentiment:
    """市场情绪容器（涨跌家数、全市场成交等）"""

    def __init__(self):
        self._lock = Lock()
        self.up_count = 0
        self.down_count = 0
        self.flat_count = 0
        self.total_count = 0
        self.last_update = None

    def update(self, up, down, flat, total):
        with self._lock:
            self.up_count = up
            self.down_count = down
            self.flat_count = flat
            self.total_count = total
            self.last_update = datetime.datetime.now()

    @property
    def up_ratio(self) -> float:
        """上涨家数占比"""
        with self._lock:
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

    def is_market_open(self) -> bool:
        """
        检查A股是否开市（周末 + ``_HOLIDAYS`` 配置的法定节假日 + 交易时段）

        Returns:
            bool: 是否开市
        """
        now = datetime.datetime.now()
        if now.weekday() >= 5:  # 周末
            return False
        if now.strftime("%Y-%m-%d") in _HOLIDAYS:  # 配置的法定节假日
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


# 创建全局市场管理器实例
market_manager = MarketManager()
