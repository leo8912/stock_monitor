#!/usr/bin/env python
"""
BaseWorker 单元测试模块

测试工作线程基类功能，包括：
- 初始化
- 启动/停止机制
- 运行状态管理
- 间隔设置
- 边界情况处理
"""

import unittest
from unittest.mock import patch

from stock_monitor.core.workers.base import BaseWorker


class MockWorker(BaseWorker):
    """用于测试的 Mock Worker"""

    def __init__(self, name="MockWorker"):
        super().__init__(name)
        self.run_called = False
        self.run_count = 0

    def run(self):
        """模拟 run 方法"""
        self.run_called = True
        self.run_count += 1


class TestBaseWorkerInitialization(unittest.TestCase):
    """BaseWorker 初始化测试"""

    def test_initialization_with_default_name(self):
        """测试使用默认名称初始化"""
        worker = BaseWorker()

        self.assertEqual(worker._name, "BaseWorker")
        self.assertFalse(worker._is_running)
        self.assertEqual(worker.interval, 60)

    def test_initialization_with_custom_name(self):
        """测试使用自定义名称初始化"""
        worker = BaseWorker("TestWorker")

        self.assertEqual(worker._name, "TestWorker")
        self.assertFalse(worker._is_running)
        self.assertEqual(worker.interval, 60)

    def test_initialization_not_running(self):
        """测试初始化时未运行状态"""
        worker = BaseWorker()

        self.assertFalse(worker.isRunning())
        self.assertFalse(worker._is_running)


class TestBaseWorkerStartStop(unittest.TestCase):
    """BaseWorker 启动/停止测试"""

    def setUp(self):
        self.worker = MockWorker("TestWorker")

    def test_start_worker(self):
        """测试启动工作线程"""
        # 初始状态
        self.assertFalse(self.worker._is_running)
        self.assertFalse(self.worker.isRunning())

        # 启动
        with patch.object(self.worker, "start") as mock_start:
            self.worker.start_worker()

            # 验证状态变化
            self.assertTrue(self.worker._is_running)
            mock_start.assert_called_once()

    def test_start_worker_already_running(self):
        """测试已运行时再次启动"""
        self.worker._is_running = True

        with patch.object(self.worker, "isRunning", return_value=True):
            with patch.object(self.worker, "start") as mock_start:
                self.worker.start_worker()

                # 不应再次启动
                mock_start.assert_not_called()

    def test_stop_worker(self):
        """测试停止工作线程"""
        self.worker._is_running = True

        with patch.object(self.worker, "wait") as mock_wait:
            mock_wait.return_value = True

            self.worker.stop_worker()

            # 验证状态变化
            self.assertFalse(self.worker._is_running)
            mock_wait.assert_called_once_with(2000)

    def test_stop_worker_sets_flag(self):
        """测试停止标志设置"""
        self.worker._is_running = True
        self.worker.stop_worker()

        self.assertFalse(self.worker._is_running)


class TestBaseWorkerRunMethod(unittest.TestCase):
    """BaseWorker run 方法测试"""

    def test_run_not_implemented(self):
        """测试未实现 run 方法抛出异常"""
        worker = BaseWorker("Test")

        with self.assertRaises(NotImplementedError) as context:
            worker.run()

        self.assertIn("子类必须实现 run 方法", str(context.exception))

    def test_run_implementation_in_subclass(self):
        """测试子类实现 run 方法"""
        worker = MockWorker()

        # 直接调用 run（不在线程中）
        worker.run()

        self.assertTrue(worker.run_called)
        self.assertEqual(worker.run_count, 1)

    def test_run_multiple_times(self):
        """测试多次调用 run"""
        worker = MockWorker()

        worker.run()
        worker.run()
        worker.run()

        self.assertEqual(worker.run_count, 3)


class TestBaseWorkerInterval(unittest.TestCase):
    """BaseWorker 间隔设置测试"""

    def test_default_interval(self):
        """测试默认间隔"""
        worker = BaseWorker()

        self.assertEqual(worker.interval, 60)

    def test_set_interval(self):
        """测试设置间隔"""
        worker = BaseWorker()

        worker.interval = 30

        self.assertEqual(worker.interval, 30)

    def test_set_interval_zero(self):
        """测试设置间隔为 0"""
        worker = BaseWorker()

        worker.interval = 0

        self.assertEqual(worker.interval, 0)

    def test_set_interval_negative(self):
        """测试设置负间隔"""
        worker = BaseWorker()

        worker.interval = -10

        self.assertEqual(worker.interval, -10)


class TestBaseWorkerStateManagement(unittest.TestCase):
    """BaseWorker 状态管理测试"""

    def setUp(self):
        self.worker = MockWorker()

    def test_is_running_flag_management(self):
        """测试运行标志管理"""
        # 初始状态
        self.assertFalse(self.worker._is_running)

        # 设置运行
        self.worker._is_running = True
        self.assertTrue(self.worker._is_running)

        # 停止
        self.worker._is_running = False
        self.assertFalse(self.worker._is_running)

    def test_name_property(self):
        """测试名称属性"""
        worker = BaseWorker("CustomName")

        self.assertEqual(worker._name, "CustomName")


class TestBaseWorkerLogging(unittest.TestCase):
    """BaseWorker 日志记录测试"""

    @patch("stock_monitor.core.workers.base.app_logger")
    def test_start_worker_logs_message(self, mock_logger):
        """测试启动时记录日志"""
        worker = BaseWorker("TestWorker")

        with patch.object(worker, "start"):
            worker.start_worker()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("TestWorker", call_args)
            self.assertIn("已启动", call_args)

    @patch("stock_monitor.core.workers.base.app_logger")
    def test_stop_worker_logs_message(self, mock_logger):
        """测试停止时记录日志"""
        worker = BaseWorker("TestWorker")
        worker._is_running = True

        with patch.object(worker, "wait", return_value=True):
            worker.stop_worker()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("TestWorker", call_args)
            self.assertIn("已停止", call_args)


class TestBaseWorkerInheritance(unittest.TestCase):
    """BaseWorker 继承测试"""

    def test_can_create_subclass(self):
        """测试可以创建子类"""

        class CustomWorker(BaseWorker):
            def run(self):
                pass

        worker = CustomWorker("Custom")

        self.assertIsInstance(worker, BaseWorker)
        self.assertEqual(worker._name, "Custom")

    def test_subclass_inherits_properties(self):
        """测试子类继承属性"""

        class CustomWorker(BaseWorker):
            def run(self):
                pass

        worker = CustomWorker("Custom")

        # 继承的属性
        self.assertEqual(worker.interval, 60)
        self.assertFalse(worker._is_running)

        # 继承的方法
        self.assertTrue(hasattr(worker, "start_worker"))
        self.assertTrue(hasattr(worker, "stop_worker"))


if __name__ == "__main__":
    unittest.main()
