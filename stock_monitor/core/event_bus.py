"""
事件总线模块
统一应用内的事件发布/订阅机制
"""

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from stock_monitor.utils.logger import app_logger


@dataclass
class Event:
    """事件基类"""

    topic: str
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


# 内置主题常量
class Topics:
    CONFIG_CHANGED = "config.changed"
    DATA_REFRESHED = "data.refreshed"
    DARK_TRADE_UPDATED = "dark_trade.updated"
    SIGNAL_GENERATED = "signal.generated"
    EXPORT_COMPLETED = "export.completed"
    HEALTH_CHECK = "health.check"
    APP_STARTUP = "app.startup"
    APP_SHUTDOWN = "app.shutdown"


class EventBus:
    """
    线程安全的事件总线

    支持：
    - 同步发布/订阅
    - 主题过滤
    - 通配符订阅（'*' 匹配所有主题）
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._wildcard_subscribers: list[Callable] = []
        self._event_lock = threading.Lock()
        self._initialized = True

    def subscribe(self, topic: str, callback: Callable) -> None:
        """
        订阅指定主题的事件

        Args:
            topic: 事件主题
            callback: 回调函数，接收 Event 参数
        """
        with self._event_lock:
            if topic == "*":
                self._wildcard_subscribers.append(callback)
            else:
                self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable) -> None:
        """取消订阅"""
        with self._event_lock:
            if topic == "*":
                self._wildcard_subscribers = [
                    cb for cb in self._wildcard_subscribers if cb != callback
                ]
            elif topic in self._subscribers:
                self._subscribers[topic] = [
                    cb for cb in self._subscribers[topic] if cb != callback
                ]

    def publish(self, topic: str, data: Any = None, source: str = "") -> None:
        """
        发布事件

        Args:
            topic: 事件主题
            data: 事件数据
            source: 事件来源标识
        """
        event = Event(topic=topic, data=data, source=source)

        # 收集所有匹配的订阅者
        subscribers = []
        with self._event_lock:
            subscribers.extend(self._subscribers.get(topic, []))
            subscribers.extend(self._wildcard_subscribers)

        # 同步执行回调
        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                app_logger.error(
                    f"事件回调异常 [{topic}]: {e}",
                    extra={"event_topic": topic, "event_source": source},
                )

    def clear(self) -> None:
        """清除所有订阅"""
        with self._event_lock:
            self._subscribers.clear()
            self._wildcard_subscribers.clear()

    def subscriber_count(self, topic: str = None) -> int:
        """获取订阅者数量"""
        with self._event_lock:
            if topic:
                return len(self._subscribers.get(topic, []))
            return sum(len(subs) for subs in self._subscribers.values()) + len(
                self._wildcard_subscribers
            )


# 全局事件总线实例
event_bus = EventBus()
