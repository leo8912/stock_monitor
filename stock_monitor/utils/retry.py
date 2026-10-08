"""
统一重试机制
基于 tenacity 库，提供标准化的重试策略
"""

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from stock_monitor.utils.logger import app_logger

# 常见网络异常
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    IOError,
    OSError,
)

# 默认重试配置
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT = 1.0
DEFAULT_MAX_WAIT = 30.0
DEFAULT_MULTIPLIER = 2.0


def _log_retry_state(retry_state: RetryCallState) -> None:
    """重试前的日志回调"""
    if retry_state.attempt_number < retry_state.retry_object.stop.max_attempt_number:
        app_logger.warning(
            f"重试 {retry_state.fn.__name__} "
            f"(第{retry_state.attempt_number}次失败，"
            f"等待{retry_state.next_action.sleep:.1f}s后重试): "
            f"{retry_state.outcome.exception()}"
        )


def network_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait: float = DEFAULT_MIN_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
    multiplier: float = DEFAULT_MULTIPLIER,
    backoff_factor: float = None,
):
    """网络请求重试装饰器（指数退避）。

    Args:
        max_attempts: 最大尝试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）
        multiplier: 退避倍数
        backoff_factor: 兼容旧接口，等同于 multiplier
    """
    if backoff_factor is not None:
        multiplier = backoff_factor
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=_log_retry_state,
        reraise=True,
    )
