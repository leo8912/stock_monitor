"""
统一配置中心
整合 ConfigManager + ConfigKeys，提供单一入口
"""

import threading
from typing import Any

from stock_monitor.config.manager import ConfigManager, load_config
from stock_monitor.core.event_bus import Topics, event_bus
from stock_monitor.utils.config_helper import ConfigKeys


class ConfigCenter:
    """
    统一配置中心

    职责：
    - 提供类型安全的配置读写
    - 配置变更时自动发布事件
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
        self._manager = ConfigManager()
        self._initialized = True

    # ── 类型安全读取 ──────────────────────────────────────────────

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._manager.get(key, default)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
        return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._manager.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(default)

    def get_str(self, key: str, default: str = "") -> str:
        value = self._manager.get(key, default)
        if isinstance(value, str):
            return value
        return str(default)

    def get_list(self, key: str, default: list | None = None) -> list:
        value = self._manager.get(key, default or [])
        if isinstance(value, list):
            return value
        return default or []

    def get(self, key: str, default: Any = None) -> Any:
        return self._manager.get(key, default)

    # ── 写入 ──────────────────────────────────────────────────────

    def set(self, key: str, value: Any, publish_event: bool = True) -> bool:
        """设置配置值并发布变更事件。"""
        success = self._manager.set(key, value)
        if success and publish_event:
            event_bus.publish(
                Topics.CONFIG_CHANGED,
                data={"key": key, "value": value},
                source="ConfigCenter",
            )
        return success

    def set_deferred(self, key: str, value: Any, publish_event: bool = True) -> bool:
        """内存立即更新、磁盘防抖写入（窗口位置等高频 UI 路径）。"""
        success = self._manager.set(key, value, flush=False)
        if success and publish_event:
            event_bus.publish(
                Topics.CONFIG_CHANGED,
                data={"key": key, "value": value},
                source="ConfigCenter",
            )
        return success

    def flush(self) -> bool:
        """冲刷防抖中的配置写盘。"""
        return self._manager.flush()

    # ── 便捷属性 ──────────────────────────────────────────────────

    @property
    def user_stocks(self) -> list[str]:
        return self.get_list(ConfigKeys.USER_STOCKS, ["sh000001"])

    @property
    def wecom_webhook(self) -> str:
        return self.get_str(ConfigKeys.WECOM_WEBHOOK, "")

    @property
    def raw(self) -> ConfigManager:
        return self._manager

    def snapshot(self) -> dict[str, Any]:
        """获取配置快照"""
        return load_config()


# 全局配置中心实例
config_center = ConfigCenter()
