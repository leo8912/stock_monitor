"""
事件总线模块
统一应用内的事件发布/订阅机制
"""

import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from stock_monitor.utils.logger import app_logger

# 尝试导入 PyQt6 以支持异步分发
_HAS_PYQT = False
try:
    from PyQt6.QtCore import QThread, QTimer

    _HAS_PYQT = True
except ImportError:
    QThread = None
    QTimer = None


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
        # 初始化并入创建锁，避免双检间隙被并发重复初始化
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._subscribers = defaultdict(list)
                    instance._wildcard_subscribers = []
                    instance._event_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

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
        发布事件。

        当前线程存在 Qt 事件 dispatcher 时，通过 ``QTimer.singleShot(0, ...)``
        异步分发回调（订阅者异常单独捕获记日志）。否则（纯 CLI / 工作线程无
        事件循环，QTimer 投递会被 Qt 静默丢弃）降级为同步执行，保证事件不丢。
        """
        event = Event(topic=topic, data=data, source=source)

        # 收集所有匹配的订阅者
        subscribers = []
        with self._event_lock:
            subscribers.extend(self._subscribers.get(topic, []))
            subscribers.extend(self._wildcard_subscribers)

        if not subscribers:
            return

        def _invoke(cb: Callable, ev: Event = event) -> None:
            try:
                cb(ev)
            except Exception as e:
                app_logger.error(
                    f"事件回调异常 [{topic}]: {e}",
                    extra={"event_topic": topic, "event_source": source},
                )

        dispatcher = None
        if _HAS_PYQT:
            # 惰性检测：导入期快照不可靠（模块导入时 QApplication 往往尚未创建）
            dispatcher = QThread.currentThread().eventDispatcher()

        if dispatcher is not None:
            for callback in subscribers:
                try:
                    QTimer.singleShot(0, lambda cb=callback: _invoke(cb))
                except Exception as e:
                    # 仅投递失败记日志并同步兜底，不与回调自身异常混淆
                    app_logger.error(
                        f"事件异步投递失败 [{topic}]，降级同步执行: {e}",
                        extra={"event_topic": topic, "event_source": source},
                    )
                    _invoke(callback)
            return

        if _HAS_PYQT:
            # QTimer 要求调用线程有事件循环，否则事件会被静默丢弃
            app_logger.error(f"当前线程无 Qt 事件循环，事件 [{topic}] 降级为同步分发")
        for callback in subscribers:
            _invoke(callback)

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
