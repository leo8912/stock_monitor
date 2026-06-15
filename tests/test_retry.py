"""Tests for retry module"""

import pytest

from stock_monitor.utils.retry import (
    network_retry,
    retry_on_failure,
    safe_retry,
)


class TestNetworkRetry:
    def test_succeeds_on_first_attempt(self):
        call_count = 0

        @network_retry(max_attempts=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        assert succeed() == "ok"
        assert call_count == 1

    def test_retries_on_connection_error(self):
        call_count = 0

        @network_retry(max_attempts=3, min_wait=0.01, max_wait=0.05)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network down")
            return "ok"

        assert fail_then_succeed() == "ok"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        @network_retry(max_attempts=2, min_wait=0.01, max_wait=0.05)
        def always_fail():
            raise ConnectionError("always fail")

        with pytest.raises(ConnectionError):
            always_fail()

    def test_does_not_retry_on_value_error(self):
        call_count = 0

        @network_retry(max_attempts=3, min_wait=0.01)
        def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            fail_with_value_error()
        assert call_count == 1


class TestSafeRetry:
    def test_custom_retry_exceptions(self):
        call_count = 0

        @safe_retry(max_attempts=2, min_wait=0.01, retry_exceptions=(ValueError,))
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retryable")
            return "ok"

        assert fail_then_succeed() == "ok"
        assert call_count == 2


class TestRetryOnFailure:
    def test_backward_compatible_decorator(self):
        call_count = 0

        @retry_on_failure(max_attempts=2, delay=0.01)
        def succeed_on_second():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("fail")
            return "ok"

        assert succeed_on_second() == "ok"
        assert call_count == 2

    def test_preserves_function_name(self):
        @retry_on_failure(max_attempts=1)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
