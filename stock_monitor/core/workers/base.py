"""Worker 基类模块"""

from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger


class BaseWorker(QtCore.QThread):
    """工作线程基类

    提供通用的启动、停止和错误处理逻辑
    所有 Worker 子类应继承此类并实现 run() 方法
    """

    def __init__(self, name: str = "BaseWorker"):
        super().__init__()
        self._name = name
        self._is_running = False
        self.interval = 60  # 默认刷新间隔（秒）

    def start_worker(self):
        """启动工作线程"""
        if not self.isRunning():
            self._is_running = True
            self.start()
            app_logger.info(f"{self._name}已启动")

    def stop_worker(self):
        """停止工作线程"""
        self._is_running = False
        self.wait(2000)
        app_logger.info(f"{self._name}已停止")

    def run(self):
        """线程执行入口

        子类必须实现此方法，在循环中执行实际业务逻辑
        应定期检查 self._is_running 标志以响应停止请求
        """
        raise NotImplementedError("子类必须实现 run 方法")
