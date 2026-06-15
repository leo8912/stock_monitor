"""
集成测试：事件总线 + 缓存 + 配置中心的端到端协作
使用 mock 避免外部依赖
"""

import os
import tempfile
import threading

from stock_monitor.core.cache_manager import LRUCache, TwoLevelCache
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


class TestCacheIntegration:
    """缓存集成测试"""

    def test_l1_to_l2_flow(self):
        """L1 缓存写入 → L2 持久化 → 新实例恢复"""
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "integration.db")

        # 写入
        cache1 = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=db_path,
            l2_ttl=3600,
            cache_name="integration_test",
        )
        cache1.set("stock:sh600000", {"price": 10.5, "name": "浦发银行"})
        cache1.set("stock:sz000001", {"price": 12.0, "name": "平安银行"})

        # 新实例从 L2 恢复
        cache2 = TwoLevelCache(
            l1_max_size=10,
            l1_ttl=60,
            l2_db_path=db_path,
            l2_ttl=3600,
            cache_name="integration_test",
        )
        assert cache2.get("stock:sh600000") == {"price": 10.5, "name": "浦发银行"}
        assert cache2.get("stock:sz000001") == {"price": 12.0, "name": "平安银行"}

    def test_l1_eviction_l2_fallback(self):
        """L1 淘汰后从 L2 回填"""
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "evict.db")

        cache = TwoLevelCache(
            l1_max_size=2,
            l1_ttl=60,
            l2_db_path=db_path,
            l2_ttl=3600,
            cache_name="evict_test",
        )
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # L1 淘汰 "a"

        # "a" 仍在 L2 中
        assert cache.get("a") == 1  # L2 回填 L1

    def test_cache_stats_tracking(self):
        """缓存命中率统计"""
        cache = TwoLevelCache(l1_max_size=10, l1_ttl=60)
        cache.set("a", 1)
        cache.get("a")  # hit
        cache.get("b")  # miss
        cache.get("c")  # miss

        stats = cache.stats
        assert stats["l1"]["hits"] == 1
        assert stats["l1"]["misses"] == 2
        assert stats["l1"]["hit_rate"] == 1 / 3


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
