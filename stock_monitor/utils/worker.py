"""
后台任务的 Qt 并发包装工具类
提供 QRunnable 包装器，替代直接使用 threading.Thread
"""

from typing import Any, Callable

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
            app_logger.error(f"后台任务 {self.func.__name__} 执行出错: {e}")
