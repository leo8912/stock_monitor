"""
集成测试：事件总线 + 缓存的端到端协作
使用 mock 避免外部依赖
"""

import threading

from stock_monitor.core.cache_manager import LRUCache
from stock_monitor.core.event_bus import EventBus, Topics


class TestEventBusIntegration:
    """事件总线端到端测试"""

    def setup_method(self):
        self.bus = EventBus()
        self.bus.clear()

    def test_config_change_propagation(self):
        """配置变更 → 事件发布 → UI 刷新链路"""
        ui_refreshed = []
        cache_cleared = []

        def on_config_changed(event):
            ui_refreshed.append(event.data)

        def on_config_clear_cache(event):
            cache_cleared.append(event.data)

        self.bus.subscribe(Topics.CONFIG_CHANGED, on_config_changed)
        self.bus.subscribe(Topics.CONFIG_CHANGED, on_config_clear_cache)

        # 模拟配置变更
        self.bus.publish(
            Topics.CONFIG_CHANGED,
            data={"key": "refresh_interval", "value": 10},
            source="SettingsDialog",
        )

        assert len(ui_refreshed) == 1
        assert len(cache_cleared) == 1
        assert ui_refreshed[0]["key"] == "refresh_interval"

    def test_dark_trade_update_flow(self):
        """暗盘数据更新 → 事件 → UI 刷新"""
        ui_updates = []
        export_triggers = []

        self.bus.subscribe(Topics.DARK_TRADE_UPDATED, lambda e: ui_updates.append(e))
        self.bus.subscribe(Topics.EXPORT_COMPLETED, lambda e: export_triggers.append(e))

        # 模拟暗盘更新
        self.bus.publish(
            Topics.DARK_TRADE_UPDATED,
            data={"stocks": ["sh600000", "sz000001"]},
            source="DarkTradeService",
        )

        assert len(ui_updates) == 1

    def test_concurrent_event_publishing(self):
        """多线程并发发布事件"""
        received = []
        lock = threading.Lock()

        def subscriber(e):
            with lock:
                received.append(e.data)

        for i in range(5):
            self.bus.subscribe(f"topic.{i}", subscriber)

        threads = []
        for i in range(5):
            for j in range(10):
                t = threading.Thread(
                    target=self.bus.publish,
                    args=(f"topic.{i}",),
                    kwargs={"data": f"{i}-{j}"},
                )
                threads.append(t)
                t.start()

        for t in threads:
            t.join()

        assert len(received) == 50


class TestEventBusAndCacheIntegration:
    """事件总线 + 缓存联动测试"""

    def test_cache_invalidation_via_event(self):
        """配置变更事件触发缓存清理"""
        cache = LRUCache(max_size=10, default_ttl=60)
        cache.set("old_config", "stale_value")

        bus = EventBus()
        bus.clear()

        def on_config_changed(event):
            cache.clear()

        bus.subscribe(Topics.CONFIG_CHANGED, on_config_changed)

        # 发布配置变更事件
        bus.publish(Topics.CONFIG_CHANGED, data={"key": "refresh_interval"})

        # 缓存应被清理
        assert cache.get("old_config") is None
