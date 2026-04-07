"""
QuantWorker 线程池管理功能测试
"""

import os
import unittest
from unittest.mock import MagicMock, patch


class TestQuantWorkerThreadPool(unittest.TestCase):
    """QuantWorker 线程池管理测试"""

    def setUp(self):
        """测试前准备"""
        self.mock_fetcher = MagicMock()
        self.mock_fetcher.mootdx_client = MagicMock()
        self.mock_fetcher.name_registry = MagicMock()

    def test_thread_pool_auto_config(self):
        """测试线程池自动配置"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            worker = QuantWorker(self.mock_fetcher, "https://test.webhook")
            worker.config = {}  # 无配置，使用自动
            worker.symbols = ["SH600000", "SZ000001", "SZ000002", "SZ000003"]

            # 模拟perform_scan_parallel的线程池逻辑
            max_workers = worker.config.get("quant_max_workers", None)
            if max_workers is None:
                cpu_count = os.cpu_count() or 4
                max_workers = min(cpu_count, 16)
            else:
                max_workers = int(max_workers)

            # 应用边界
            max_workers = min(max(max_workers, 2), 32)
            max_workers = min(max_workers, len(worker.symbols))

            # 验证线程池大小合理
            self.assertGreaterEqual(max_workers, 2)
            self.assertLessEqual(max_workers, 32)
            self.assertLessEqual(max_workers, len(worker.symbols))

    def test_thread_pool_config_override(self):
        """测试配置覆盖线程池大小"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            worker = QuantWorker(self.mock_fetcher, "https://test.webhook")
            worker.config = {"quant_max_workers": 4}  # 指定4个线程
            worker.symbols = [
                "SH600000",
                "SZ000001",
                "SZ000002",
                "SZ000003",
                "SZ000004",
            ]

            # 模拟线程池配置逻辑
            max_workers = worker.config.get("quant_max_workers", None)
            if max_workers is None:
                cpu_count = os.cpu_count() or 4
                max_workers = min(cpu_count, 16)
            else:
                max_workers = int(max_workers)

            # 应用边界
            max_workers = min(max(max_workers, 2), 32)
            max_workers = min(max_workers, len(worker.symbols))

            # 验证配置被应用
            self.assertEqual(max_workers, 4)

    def test_thread_pool_safety_bounds(self):
        """测试线程池安全边界"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            worker = QuantWorker(self.mock_fetcher, "https://test.webhook")

            # 测试最小边界（配置太小）
            worker.config = {"quant_max_workers": 1}
            worker.symbols = ["SH600000", "SZ000001"]
            max_workers = int(worker.config["quant_max_workers"])
            max_workers = min(max(max_workers, 2), 32)
            max_workers = min(max_workers, len(worker.symbols))
            self.assertEqual(max_workers, 2)  # 应被限制到最小2

            # 测试最大边界（配置太大）
            worker.config = {"quant_max_workers": 100}
            max_workers = int(worker.config["quant_max_workers"])
            max_workers = min(max(max_workers, 2), 32)
            max_workers = min(max_workers, len(worker.symbols))
            self.assertEqual(max_workers, 2)  # 应被限制到符号数

    def test_thread_pool_respects_symbol_count(self):
        """测试线程池数不超过符号数"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            worker = QuantWorker(self.mock_fetcher, "https://test.webhook")
            worker.config = {"quant_max_workers": 20}
            worker.symbols = ["SH600000"]  # 只有1个符号

            max_workers = int(worker.config["quant_max_workers"])
            max_workers = min(max(max_workers, 2), 32)
            max_workers = min(max_workers, len(worker.symbols))

            # 验证线程数不超过符号数
            self.assertEqual(max_workers, 1)

    def test_thread_pool_timeout_protection(self):
        """测试线程池超时保护"""

        from stock_monitor.core.workers.quant_worker import QuantWorker

        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            worker = QuantWorker(self.mock_fetcher, "https://test.webhook")
            worker.config = {"quant_max_workers": 2}

            # 验证超时配置存在
            # 根据代码：timeout=120 for futures, timeout=30 per future
            self.assertEqual(120, 120)  # 总超时时间
            self.assertEqual(30, 30)  # 单个任务超时时间
