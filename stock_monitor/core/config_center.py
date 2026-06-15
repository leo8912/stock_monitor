"""
统一配置中心
整合 ConfigManager + ConfigHelper + ConfigKeys，提供单一入口
"""

import threading
from typing import Any

from stock_monitor.config.manager import ConfigManager, load_config, save_config
from stock_monitor.core.event_bus import Topics, event_bus
from stock_monitor.utils.config_helper import ConfigHelper, ConfigKeys


class ConfigCenter:
    """
    统一配置中心

    职责：
    - 提供类型安全的配置读写
    - 配置变更时自动发布事件
    - 缓存常用配置值，减少 I/O
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
        self._helper = ConfigHelper(self._manager)
        self._cache: dict[str, Any] = {}
        self._cache_lock = threading.Lock()
        self._initialized = True

    # ── 类型安全读取 ──────────────────────────────────────────────

    def get_str(self, key: str, default: str = "") -> str:
        return self._helper.get_str(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        return self._helper.get_int(key, default)

    def get_float(self, key: str, default: float = 0.0) -> float:
        return self._helper.get_float(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self._helper.get_bool(key, default)

    def get_list(self, key: str, default: list = None) -> list:
        return self._helper.get_list(key, default or [])

    def get(self, key: str, default: Any = None) -> Any:
        return self._manager.get(key, default)

    # ── 写入 ──────────────────────────────────────────────────────

    def set(self, key: str, value: Any, publish_event: bool = True) -> bool:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            publish_event: 是否发布变更事件
        """
        success = self._manager.set(key, value)
        if success and publish_event:
            event_bus.publish(
                Topics.CONFIG_CHANGED,
                data={"key": key, "value": value},
                source="ConfigCenter",
            )
        return success

    def update(self, config: dict[str, Any], publish_event: bool = True) -> bool:
        """批量更新配置"""
        success = save_config(config)
        if success and publish_event:
            event_bus.publish(
                Topics.CONFIG_CHANGED,
                data={"keys": list(config.keys())},
                source="ConfigCenter",
            )
        return success

    # ── 便捷属性 ──────────────────────────────────────────────────

    @property
    def user_stocks(self) -> list[str]:
        return self.get_list(ConfigKeys.USER_STOCKS, ["sh000001"])

    @property
    def refresh_interval(self) -> int:
        return self.get_int(ConfigKeys.REFRESH_INTERVAL, 5)

    @property
    def quant_enabled(self) -> bool:
        return self.get_bool(ConfigKeys.QUANT_ENABLED, False)

    @property
    def push_mode(self) -> str:
        return self.get_str(ConfigKeys.PUSH_MODE, "webhook")

    @property
    def wecom_webhook(self) -> str:
        return self.get_str(ConfigKeys.WECOM_WEBHOOK, "")

    @property
    def wecom_corpid(self) -> str:
        return self.get_str(ConfigKeys.WECOM_CORPID, "")

    @property
    def wecom_corpsecret(self) -> str:
        return self.get_str(ConfigKeys.WECOM_CORPSECRET, "")

    @property
    def wecom_agentid(self) -> str:
        return self.get_str(ConfigKeys.WECOM_AGENTID, "")

    # ── 原始访问（兼容旧代码）─────────────────────────────────────

    @property
    def raw(self) -> ConfigManager:
        return self._manager

    def snapshot(self) -> dict[str, Any]:
        """获取配置快照"""
        return load_config()


# 全局配置中心实例
config_center = ConfigCenter()
