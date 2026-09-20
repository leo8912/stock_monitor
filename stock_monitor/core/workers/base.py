"""Worker 基类模块"""

import threading

from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger

# 停止等待默认上限（毫秒）与轮询间隔（毫秒）
DEFAULT_STOP_TIMEOUT_MS = 15000
STOP_POLL_INTERVAL_MS = 100


def wait_for_thread_stop(
    thread: "QtCore.QThread",
    timeout_ms: int = DEFAULT_STOP_TIMEOUT_MS,
    interval_ms: int = STOP_POLL_INTERVAL_MS,
) -> bool:
    """轮询等待 QThread 真正结束。

    替代一次性 ``wait(固定值)``：分段等待并周期性检查 ``isRunning()``，既能在
    线程及时退出时快速返回，也能在网络重试等慢任务下等待更久。

    Args:
        thread: 目标 QThread。
        timeout_ms: 最长等待毫秒数。
        interval_ms: 单次轮询等待毫秒数。

    Returns:
        bool: 线程在超时前结束返回 True，否则 False。
    """
    if not thread.isRunning():
        return True

    elapsed_ms = 0
    while thread.isRunning() and elapsed_ms < timeout_ms:
        # thread.wait 返回 True 表示线程已结束
        if thread.wait(interval_ms):
            return True
        elapsed_ms += interval_ms
    return not thread.isRunning()


class BaseWorker(QtCore.QThread):
    """工作线程基类

    提供通用的启动、停止和错误处理逻辑
    所有 Worker 子类应继承此类并实现 run() 方法
    """

    def __init__(self, name: str = "BaseWorker") -> None:
        """初始化工作线程基类。

        Args:
            name: 线程名称，用于日志标识。
        """
        super().__init__()
        self._name = name
        self._is_running = False
        self._lock = threading.Lock()
        self.interval = 60  # 默认刷新间隔（秒）

    def start_worker(self) -> None:
        """启动工作线程"""
        with self._lock:
            if not self.isRunning():
                self._is_running = True
                self.start()
                app_logger.info(f"{self._name}已启动")

    def stop_worker(self) -> None:
        """停止工作线程。

        设置停止标志后轮询等待线程真正结束（最长 ``DEFAULT_STOP_TIMEOUT_MS``），
        超时仅告警而不阻塞退出。
        """
        with self._lock:
            self._is_running = False
        if not wait_for_thread_stop(self):
            app_logger.warning(
                f"{self._name} 停止超时（>{DEFAULT_STOP_TIMEOUT_MS}ms），线程可能仍在收尾"
            )
        app_logger.info(f"{self._name}已停止")

    def run(self) -> None:
        """线程执行入口

        子类必须实现此方法，在循环中执行实际业务逻辑
        应定期检查 self._is_running 标志以响应停止请求
        """
        raise NotImplementedError("子类必须实现 run 方法")
