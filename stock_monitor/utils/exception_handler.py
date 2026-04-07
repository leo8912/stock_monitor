"""
增强的异常处理系统 - P1改进
包含：异常分类、装饰器、降级策略、日志记录
"""

import functools
import time
from enum import Enum
from typing import Any, Callable, Optional

from .logger import app_logger


class ExceptionCategory(Enum):
    """异常分类枚举"""

    NETWORK = "network"  # 网络故障（超时、连接拒绝等）
    DATA_ERROR = "data_error"  # 数据错误（格式、验证等）
    RESOURCE_ERROR = "resource"  # 资源错误（内存、磁盘等）
    LOGIC_ERROR = "logic"  # 逻辑错误（不应该发生）
    EXTERNAL_API = "external"  # 外部API错误（股票数据源等）
    UNKNOWN = "unknown"  # 未知错误


class ApplicationException(Exception):
    """应用基础异常类"""

    def __init__(
        self,
        message: str,
        category: ExceptionCategory = ExceptionCategory.UNKNOWN,
        original_exception: Optional[Exception] = None,
        context: Optional[dict] = None,
    ):
        self.message = message
        self.category = category
        self.original_exception = original_exception
        self.context = context or {}
        super().__init__(self.message)

    def __str__(self):
        parts = [f"[{self.category.value.upper()}] {self.message}"]
        if self.original_exception:
            parts.append(f"原因: {str(self.original_exception)}")
        if self.context:
            parts.append(f"上下文: {self.context}")
        return " | ".join(parts)


class NetworkException(ApplicationException):
    """网络异常"""

    def __init__(
        self, message: str, original_exception: Optional[Exception] = None, **kwargs
    ):
        super().__init__(message, ExceptionCategory.NETWORK, original_exception, kwargs)


class DataValidationException(ApplicationException):
    """数据验证异常"""

    def __init__(
        self, message: str, original_exception: Optional[Exception] = None, **kwargs
    ):
        super().__init__(
            message, ExceptionCategory.DATA_ERROR, original_exception, kwargs
        )


class ExternalAPIException(ApplicationException):
    """外部API异常"""

    def __init__(
        self, message: str, original_exception: Optional[Exception] = None, **kwargs
    ):
        super().__init__(
            message, ExceptionCategory.EXTERNAL_API, original_exception, kwargs
        )


def classify_exception(exc: Exception) -> ExceptionCategory:
    """根据异常类型分类异常"""
    exc_type_name = type(exc).__name__
    exc_str = str(exc).lower()

    # 网络异常
    network_keywords = ["timeout", "connection", "refused", "host", "network", "socket"]
    if any(kw in exc_str for kw in network_keywords):
        return ExceptionCategory.NETWORK
    if exc_type_name in ["TimeoutError", "ConnectionError", "OSError"]:
        return ExceptionCategory.NETWORK

    # 数据错误
    data_keywords = ["value", "key", "index", "type", "parse"]
    if any(kw in exc_str for kw in data_keywords):
        return ExceptionCategory.DATA_ERROR
    if exc_type_name in ["ValueError", "KeyError", "IndexError", "TypeError"]:
        return ExceptionCategory.DATA_ERROR

    # 资源错误
    if exc_type_name in ["MemoryError", "OSError", "IOError"]:
        return ExceptionCategory.RESOURCE_ERROR

    # 外部API错误
    if "api" in exc_str or "requests" in exc_str or exc_type_name in ["HTTPError"]:
        return ExceptionCategory.EXTERNAL_API

    return ExceptionCategory.UNKNOWN


def handle_exception(
    func: Callable,
    exc: Exception,
    context: Optional[dict] = None,
    default_return: Any = None,
    fallback_strategy: Optional[Callable] = None,
) -> Any:
    """
    统一异常处理函数

    Args:
        func: 发生异常的函数
        exc: 异常对象
        context: 上下文信息
        default_return: 默认返回值
        fallback_strategy: 降级策略（可选的可调用对象）

    Returns:
        返回值或None
    """
    category = classify_exception(exc)

    # 记录详细日志
    log_msg = f"函数 {func.__name__} 发生 {category.value} 异常: {exc}"
    if context:
        log_msg += f" (上下文: {context})"

    if category == ExceptionCategory.NETWORK:
        app_logger.warning(f"[网络异常] {log_msg} - 将尝试降级")
    elif category == ExceptionCategory.DATA_ERROR:
        app_logger.error(f"[数据错误] {log_msg}")
    elif category == ExceptionCategory.EXTERNAL_API:
        app_logger.warning(f"[外部API异常] {log_msg}")
    else:
        app_logger.error(f"[{category.value}] {log_msg}")

    # 尝试降级策略
    if fallback_strategy is not None:
        try:
            result = fallback_strategy()
            app_logger.info(f"降级策略执行成功: {func.__name__}")
            return result
        except Exception as fallback_exc:
            app_logger.error(f"降级策略也失败了: {fallback_exc}")

    return default_return


def safe_call(
    max_retries: int = 0,
    default_return: Any = None,
    fallback_strategy: Optional[Callable] = None,
    on_exception_callback: Optional[Callable] = None,
    catch_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    装饰器：添加异常处理和重试能力

    Args:
        max_retries: 最大重试次数（0表示不重试）
        default_return: 异常时的默认返回值
        fallback_strategy: 降级策略
        on_exception_callback: 异常回调（用于记录、上报等）
        catch_exceptions: 要捕获的异常类型

    Example:
        @safe_call(max_retries=2, default_return=0)
        def risky_func():
            return 1 / 0
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    return result
                except catch_exceptions as exc:
                    # 执行异常回调
                    if on_exception_callback:
                        try:
                            on_exception_callback(
                                func.__name__, exc, attempt, max_retries
                            )
                        except Exception as cb_exc:
                            app_logger.warning(f"异常回调失败: {cb_exc}")

                    # 如果还有重试次数，继续重试
                    if attempt < max_retries:
                        wait_time = 0.5 * (2**attempt)  # 指数退避
                        app_logger.warning(
                            f"{func.__name__} 重试 {attempt + 1}/{max_retries}, "
                            f"{wait_time:.1f}秒后再试. 异常: {exc}"
                        )
                        time.sleep(wait_time)
                    else:
                        # 重试次数用尽，尝试降级
                        return handle_exception(
                            func,
                            exc,
                            context={"args": args, "kwargs": kwargs},
                            default_return=default_return,
                            fallback_strategy=fallback_strategy,
                        )

            # 失败返回默认值
            return default_return

        return wrapper

    return decorator


def log_exception(log_level: str = "error", include_traceback: bool = True):
    """
    装饰器：记录函数异常为日志

    Args:
        log_level: 日志级别 ("debug", "info", "warning", "error")
        include_traceback: 是否包含完整堆栈跟踪
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                category = classify_exception(exc)
                msg = f"{func.__name__} 异常 [{category.value}]: {exc}"

                if include_traceback:
                    import traceback

                    msg += f"\n堆栈:\n{traceback.format_exc()}"

                log_func = getattr(app_logger, log_level, app_logger.error)
                log_func(msg)
                raise

        return wrapper

    return decorator
