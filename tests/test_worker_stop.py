#!/usr/bin/env python
"""Worker 停止逻辑回归测试（T05）。

验证：
- 轮询式停止会等待"慢任务"线程真正结束（不是固定 wait(2000) 误判）
- QuantWorker.stop_worker 不再关闭单例数据库连接池
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets  # noqa: E402

from stock_monitor.core.workers.base import BaseWorker  # noqa: E402
from stock_monitor.core.workers.quant_worker import QuantWorker  # noqa: E402
from stock_monitor.data.stock.stock_db import StockDatabase  # noqa: E402

# 慢任务时长（秒）——远大于旧的固定 wait(2000)
SLOW_TASK_SECONDS = 6


def _get_qapp() -> QtWidgets.QApplication:
    """获取或创建全局 QApplication（离屏模式）。"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _SlowBaseWorker(BaseWorker):
    """模拟慢任务：run 阻塞后退出。"""

    def run(self):
        self.msleep(SLOW_TASK_SECONDS * 1000)


class _SlowQuantWorker(QuantWorker):
    """模拟慢任务：run 阻塞后退出（不触碰数据库）。"""

    def run(self):
        self.msleep(SLOW_TASK_SECONDS * 1000)


class TestBaseWorkerPollingStop(unittest.TestCase):
    """BaseWorker 轮询式停止测试。"""

    def setUp(self):
        self.app = _get_qapp()

    def test_stop_waits_for_slow_task(self):
        """慢任务下 stop_worker 返回时线程必须已结束（等待 > 2 秒）。"""
        worker = _SlowBaseWorker("SlowBase")
        worker.start()
        time.sleep(0.4)  # 确保线程已进入慢任务

        start = time.time()
        worker.stop_worker()
        elapsed = time.time() - start

        self.assertFalse(worker.isRunning())
        # 固定 wait(2000) 会在约 2 秒后误判为"已停止"；轮询必须等到真正结束
        self.assertGreater(elapsed, 2.0)


class TestQuantWorkerStopDoesNotCloseDatabase(unittest.TestCase):
    """QuantWorker 停止时不得关闭单例数据库。"""

    def setUp(self):
        self.app = _get_qapp()

    def test_stop_worker_does_not_close_database(self):
        """stop_worker 返回后线程停止，且 StockDatabase.close 未被调用。"""
        close_calls = []

        def _record_close(instance):
            close_calls.append(instance)

        with patch.object(QuantWorker, "_load_signal_cache", lambda self: None):
            with patch.object(QuantWorker, "_save_signal_cache", lambda self: None):
                worker = _SlowQuantWorker(MagicMock(), "")

        # 修复后不再持有 self.db 字段
        self.assertFalse(hasattr(worker, "db"))

        worker.start()
        time.sleep(0.4)

        start = time.time()
        with patch.object(StockDatabase, "close", _record_close):
            worker.stop_worker()
        elapsed = time.time() - start

        self.assertFalse(worker.isRunning())
        self.assertGreater(elapsed, 2.0)
        self.assertEqual(close_calls, [], "stop_worker 不应关闭全局数据库连接池")


if __name__ == "__main__":
    unittest.main()
