"""
错误处理和异常管理模块
"""

from typing import Any, Callable

from .logger import app_logger
from .retry import retry_on_failure  # noqa: F401 - 向后兼容导出

# 定义常见的异常类型
NETWORK_ERROR_TYPES = (ConnectionError, TimeoutError, IOError)
VALIDATION_ERROR_TYPES = (ValueError, TypeError)


def safe_call(
    func: Callable, *args, default_return=None, exception_handler=None, **kwargs
) -> Any:
    """
    安全调用函数，捕获并记录异常

    Args:
        func: 要调用的函数
        *args: 函数的位置参数
        default_return: 发生异常时的默认返回值
        exception_handler: 自定义异常处理函数
        **kwargs: 函数的关键字参数

    Returns:
        函数返回值或默认返回值
    """
    captured_exception = None
    try:
        return func(*args, **kwargs)
    except NETWORK_ERROR_TYPES as e:
        captured_exception = e
        error_type = "network"
        error_msg = f"调用函数 {func.__name__} 时发生网络错误: {e}"
    except VALIDATION_ERROR_TYPES as e:
        captured_exception = e
        error_type = "validation"
        error_msg = f"调用函数 {func.__name__} 时发生数据验证错误: {e}"
    except Exception as e:
        captured_exception = e
        error_type = "unknown"
        error_msg = f"调用函数 {func.__name__} 时发生未知错误: {e}"

    # 统一的错误日志记录
    app_logger.error(error_msg)
    app_logger.debug(f"函数参数: args={args}, kwargs={kwargs}")

    # 调用自定义异常处理器(如果提供)
    if exception_handler:
        return exception_handler(captured_exception, error_type)

    return default_return


# 注意：不再在模块级设置 sys.excepthook，
# 异常钩子由 Application._setup_exception_hook 统一管理，
# 避免多处覆盖导致行为不一致。
