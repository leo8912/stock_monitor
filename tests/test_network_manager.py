"""NetworkManager 统一 HTTP 客户端测试

覆盖：显式 timeout、共享 utils.retry 重试策略、失败返回 None、
线程本地 Session 隔离。
"""

from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

import requests

from stock_monitor.network.manager import NetworkManager


def _ok_response(status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status.return_value = None
    return resp


class TestNetworkManagerTimeout(unittest.TestCase):
    def test_default_timeout_applied(self):
        nm = NetworkManager(timeout=7, enable_retry=False)
        session = MagicMock()
        session.request.return_value = _ok_response()
        with patch.object(nm, "_session", return_value=session):
            result = nm.get("https://example.com/api")
        self.assertIsNotNone(result)
        _, kwargs = session.request.call_args
        self.assertEqual(kwargs["timeout"], 7)

    def test_explicit_timeout_overrides_default(self):
        nm = NetworkManager(timeout=7, enable_retry=False)
        session = MagicMock()
        session.request.return_value = _ok_response()
        with patch.object(nm, "_session", return_value=session):
            nm.get("https://example.com/api", timeout=3)
        _, kwargs = session.request.call_args
        self.assertEqual(kwargs["timeout"], 3)

    def test_connect_read_tuple_timeout_passed_through(self):
        nm = NetworkManager(timeout=(15, 30), enable_retry=False)
        session = MagicMock()
        session.request.return_value = _ok_response()
        with patch.object(nm, "_session", return_value=session):
            nm.get("https://example.com/pkg.zip", stream=True)
        _, kwargs = session.request.call_args
        self.assertEqual(kwargs["timeout"], (15, 30))
        self.assertTrue(kwargs["stream"])


class TestNetworkManagerRetry(unittest.TestCase):
    """客户端默认走 utils.retry.network_retry 共享策略。"""

    def test_retries_transient_connection_error(self):
        nm = NetworkManager(timeout=1, max_attempts=3)
        session = MagicMock()
        session.request.side_effect = [
            ConnectionError("boom"),
            ConnectionError("boom"),
            _ok_response(),
        ]
        with patch.object(nm, "_session", return_value=session):
            with (
                patch("stock_monitor.network.manager._RETRY_MIN_WAIT", 0.01),
                patch("stock_monitor.network.manager._RETRY_MAX_WAIT", 0.02),
            ):
                result = nm.get("https://example.com/api")
        self.assertIsNotNone(result)
        self.assertEqual(session.request.call_count, 3)

    def test_returns_none_after_retry_exhausted(self):
        nm = NetworkManager(timeout=1, max_attempts=2)
        session = MagicMock()
        session.request.side_effect = ConnectionError("always down")
        with patch.object(nm, "_session", return_value=session):
            with (
                patch("stock_monitor.network.manager._RETRY_MIN_WAIT", 0.01),
                patch("stock_monitor.network.manager._RETRY_MAX_WAIT", 0.02),
            ):
                result = nm.get("https://example.com/api")
        self.assertIsNone(result)
        self.assertEqual(session.request.call_count, 2)

    def test_enable_retry_false_single_attempt(self):
        nm = NetworkManager(timeout=1, enable_retry=False)
        session = MagicMock()
        session.request.side_effect = ConnectionError("down")
        with patch.object(nm, "_session", return_value=session):
            result = nm.get("https://example.com/api")
        self.assertIsNone(result)
        self.assertEqual(session.request.call_count, 1)

    def test_per_call_enable_retry_override(self):
        nm = NetworkManager(timeout=1, enable_retry=False, max_attempts=2)
        session = MagicMock()
        session.request.side_effect = [
            ConnectionError("down"),
            _ok_response(),
        ]
        with patch.object(nm, "_session", return_value=session):
            with (
                patch("stock_monitor.network.manager._RETRY_MIN_WAIT", 0.01),
                patch("stock_monitor.network.manager._RETRY_MAX_WAIT", 0.02),
            ):
                result = nm.get("https://example.com/api", enable_retry=True)
        # enable_retry 作为 kwarg 弹出，不应传给 requests
        self.assertIsNotNone(result)
        self.assertEqual(session.request.call_count, 2)
        _, kwargs = session.request.call_args
        self.assertNotIn("enable_retry", kwargs)

    def test_http_error_returns_none(self):
        nm = NetworkManager(timeout=1, enable_retry=False)
        session = MagicMock()
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        session.request.return_value = resp
        with patch.object(nm, "_session", return_value=session):
            result = nm.get("https://example.com/missing")
        self.assertIsNone(result)


class TestNetworkManagerThreadLocalSession(unittest.TestCase):
    def test_sessions_are_thread_local(self):
        nm = NetworkManager(timeout=1, enable_retry=False)
        sessions: list = []
        barrier = threading.Barrier(2, timeout=5)

        def worker():
            sessions.append(nm._session())
            barrier.wait()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertEqual(len(sessions), 2)
        self.assertIsNot(sessions[0], sessions[1])

    def test_same_thread_reuses_session(self):
        nm = NetworkManager(timeout=1, enable_retry=False)
        s1 = nm._session()
        s2 = nm._session()
        self.assertIs(s1, s2)

    def test_close_releases_tracked_sessions(self):
        nm = NetworkManager(timeout=1, enable_retry=False)
        s = nm._session()
        with patch.object(s, "close") as mock_close:
            nm.close()
        mock_close.assert_called_once()


class TestNetworkManagerPost(unittest.TestCase):
    def test_post_uses_shared_retry_and_timeout(self):
        nm = NetworkManager(timeout=9, max_attempts=2)
        session = MagicMock()
        session.request.side_effect = [
            ConnectionError("reset"),
            _ok_response(),
        ]
        with patch.object(nm, "_session", return_value=session):
            with (
                patch("stock_monitor.network.manager._RETRY_MIN_WAIT", 0.01),
                patch("stock_monitor.network.manager._RETRY_MAX_WAIT", 0.02),
            ):
                result = nm.post("https://example.com/hook", json={"a": 1})
        self.assertIsNotNone(result)
        self.assertEqual(session.request.call_count, 2)
        args, kwargs = session.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(kwargs["timeout"], 9)


if __name__ == "__main__":
    unittest.main()
