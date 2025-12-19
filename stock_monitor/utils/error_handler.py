"""
错误处理和异常管理模块
"""

import traceback
import sys
from typing import Optional, Callable, Any
from .logger import app_logger

# 定义常见的异常类型
NETWORK_ERROR_TYPES = (ConnectionError, TimeoutError, IOError)
VALIDATION_ERROR_TYPES = (ValueError, TypeError)

class ErrorHandler:
    """错误处理器"""
    
    @staticmethod
    def handle_exception(exc_type, exc_value, exc_traceback):
        """
        全局异常处理函数
        
        Args:
            exc_type: 异常类型
            exc_value: 异常值
            exc_traceback: 异常追踪信息
        """
        if issubclass(exc_type, KeyboardInterrupt):
            # 允许键盘中断正常处理
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # 记录详细的错误信息
        error_msg = f"未捕获的异常: {exc_type.__name__}: {exc_value}"
        app_logger.error(error_msg)
        
        # 记录详细的堆栈追踪信息
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_text = ''.join(tb_lines)
        app_logger.error(f"堆栈追踪:\n{tb_text}")
        
        # 打印到控制台
        app_logger.error(f"错误: {error_msg}")
        app_logger.error(f"堆栈追踪:\n{tb_text}")

def safe_call(func: Callable, *args, default_return=None, exception_handler=None, **kwargs) -> Any:
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
    try:
        return func(*args, **kwargs)
    except NETWORK_ERROR_TYPES as e:
        error_msg = f"调用函数 {func.__name__} 时发生网络错误: {e}"
        app_logger.error(error_msg)
        app_logger.debug(f"函数参数: args={args}, kwargs={kwargs}")
        if exception_handler:
            return exception_handler(e, 'network')
        return default_return
    except VALIDATION_ERROR_TYPES as e:
        error_msg = f"调用函数 {func.__name__} 时发生数据验证错误: {e}"
        app_logger.error(error_msg)
        app_logger.debug(f"函数参数: args={args}, kwargs={kwargs}")
        if exception_handler:
            return exception_handler(e, 'validation')
        return default_return
    except Exception as e:
        error_msg = f"调用函数 {func.__name__} 时发生未知错误: {e}"
        app_logger.error(error_msg)
        app_logger.debug(f"函数参数: args={args}, kwargs={kwargs}")
        app_logger.error(error_msg)
        if exception_handler:
            return exception_handler(e, 'unknown')
        return default_return

def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """
    重试装饰器，在函数失败时自动重试
    
    Args:
        max_attempts: 最大尝试次数
        delay: 重试间隔（秒）
    """
    import time
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = Exception("未知错误")  # 默认异常
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    warning_msg = f"函数 {func.__name__} 第{attempt + 1}次尝试失败: {e}"
                    app_logger.warning(warning_msg)
                    if attempt < max_attempts - 1:  # 不是最后一次尝试
                        app_logger.info(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
            
            # 所有尝试都失败了
            error_msg = f"函数 {func.__name__} 在 {max_attempts} 次尝试后仍然失败"
            app_logger.error(error_msg)
            raise last_exception
        
        return wrapper
    return decorator

# 设置全局异常处理器
sys.excepthook = ErrorHandler.handle_exception