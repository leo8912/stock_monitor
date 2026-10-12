"""
后台任务的 Qt 并发包装工具类
提供 QRunnable 包装器，替代直接使用 threading.Thread
"""

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QRunnable, pyqtSlot

from stock_monitor.utils.logger import app_logger


class WorkerRunnable(QRunnable):
    """
    通用后台任务的 QRunnable 包装器
    用于将普通函数提交到 QThreadPool 执行
    """

    def __init__(self, func: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        """执行任务"""
        try:
            self.func(*self.args, **self.kwargs)
        except Exception as e:
            # functools.partial / 可调用实例可能没有 __name__，避免错误处理本身再抛异常
            func_name = getattr(self.func, "__name__", repr(self.func))
            app_logger.error(f"后台任务 {func_name} 执行出错: {e}")
