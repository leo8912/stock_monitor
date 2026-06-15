"""Tests for EventBus"""

import threading

from stock_monitor.core.event_bus import EventBus, Topics


class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()
        self.bus.clear()

    def test_subscribe_and_publish(self):
        received = []
        self.bus.subscribe("test.topic", lambda e: received.append(e))
        self.bus.publish("test.topic", data="hello")

        assert len(received) == 1
        assert received[0].topic == "test.topic"
        assert received[0].data == "hello"

    def test_wildcard_subscription(self):
        received = []
        self.bus.subscribe("*", lambda e: received.append(e))
        self.bus.publish("any.topic", data=1)
        self.bus.publish("another.topic", data=2)

        assert len(received) == 2

    def test_unsubscribe(self):
        received = []

        def callback(e):
            received.append(e)

        self.bus.subscribe("test", callback)
        self.bus.publish("test", data=1)
        assert len(received) == 1

        self.bus.unsubscribe("test", callback)
        self.bus.publish("test", data=2)
        assert len(received) == 1  # no new event

    def test_multiple_subscribers(self):
        results = {"a": 0, "b": 0}
        self.bus.subscribe("t", lambda e: results.__setitem__("a", results["a"] + 1))
        self.bus.subscribe("t", lambda e: results.__setitem__("b", results["b"] + 1))
        self.bus.publish("t")

        assert results["a"] == 1
        assert results["b"] == 1

    def test_callback_exception_does_not_break_others(self):
        results = []

        def bad_callback(e):
            raise RuntimeError("boom")

        def good_callback(e):
            results.append("ok")

        self.bus.subscribe("t", bad_callback)
        self.bus.subscribe("t", good_callback)
        self.bus.publish("t")

        assert results == ["ok"]

    def test_publish_with_source(self):
        received = []
        self.bus.subscribe("t", lambda e: received.append(e))
        self.bus.publish("t", source="test_module")

        assert received[0].source == "test_module"

    def test_clear(self):
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe("b", lambda e: None)
        self.bus.clear()

        assert self.bus.subscriber_count("a") == 0
        assert self.bus.subscriber_count("b") == 0

    def test_subscriber_count(self):
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe("a", lambda e: None)
        self.bus.subscribe("b", lambda e: None)

        assert self.bus.subscriber_count("a") == 2
        assert self.bus.subscriber_count() == 3

    def test_singleton(self):
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    def test_thread_safety(self):
        received = []
        lock = threading.Lock()

        def subscriber(e):
            with lock:
                received.append(e.data)

        self.bus.subscribe("concurrent", subscriber)

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=self.bus.publish, args=("concurrent",), kwargs={"data": i}
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(received) == 10
        assert sorted(received) == list(range(10))

    def test_topics_constants(self):
        assert Topics.CONFIG_CHANGED == "config.changed"
        assert Topics.DATA_REFRESHED == "data.refreshed"
        assert Topics.APP_STARTUP == "app.startup"
