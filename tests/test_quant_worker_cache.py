"""
QuantWorker 信号缓存持久化功能测试
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestQuantWorkerCachePersistence(unittest.TestCase):
    """QuantWorker 缓存持久化测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时目录用于测试缓存文件
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.cache_file = self.cache_dir / "signal_cache.json"

    def tearDown(self):
        """测试后清理"""
        self.temp_dir.cleanup()

    def test_load_signal_cache_file_not_exists(self):
        """测试缓存文件不存在时的初始化"""
        # 模拟 QuantWorker
        from stock_monitor.core.workers.quant_worker import QuantWorker

        # 创建mock的stock_fetcher
        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with patch(
            "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
            self.cache_file,
        ):
            # 确保缓存文件不存在
            self.assertFalse(self.cache_file.exists())

            # 创建 QuantWorker 实例
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")

            # 验证缓存为空
            self.assertEqual(len(worker._last_signal_time), 0)
            self.assertEqual(worker._last_signal_time, {})

    def test_save_signal_cache_creates_file(self):
        """测试保存信号缓存创建文件"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with (
            patch(
                "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
                self.cache_file,
            ),
            patch("stock_monitor.core.workers.quant_worker.CACHE_DIR", self.cache_dir),
        ):
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")

            # 手动添加一些信号缓存
            now = time.time()
            worker._last_signal_time[("SH600000", "Daily:MACD底背离")] = now
            worker._last_signal_time[("SZ000001", "Daily:RSI超卖")] = now - 100

            # 保存缓存
            worker._save_signal_cache()

            # 验证文件已创建
            self.assertTrue(self.cache_file.exists())

            # 验证文件内容
            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(len(data), 2)
            self.assertIn("SH600000::Daily:MACD底背离", data)
            self.assertIn("SZ000001::Daily:RSI超卖", data)

    def test_load_signal_cache_restores_data(self):
        """测试加载缓存恢复数据"""
        # 先创建一个缓存文件
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cache_data = {
            "SH600000::Daily:MACD底背离": now,
            "SZ000001::Daily:RSI超卖": now - 100,
        }

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        # 创建 QuantWorker 并加载缓存
        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with patch(
            "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
            self.cache_file,
        ):
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")

        # 验证缓存已恢复
        self.assertEqual(len(worker._last_signal_time), 2)
        self.assertIn(("SH600000", "Daily:MACD底背离"), worker._last_signal_time)
        self.assertIn(("SZ000001", "Daily:RSI超卖"), worker._last_signal_time)

    def test_load_signal_cache_removes_expired_entries(self):
        """测试加载缓存时清理过期项"""
        # 创建包含过期项的缓存文件
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        cache_data = {
            "SH600000::Daily:MACD底背离": now,  # 活跃项
            "SZ000001::Daily:RSI超卖": now - 100000,  # 过期项（超过24小时）
        }

        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        # 创建 QuantWorker 并加载缓存
        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with patch(
            "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
            self.cache_file,
        ):
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")

        # 验证过期项已被清理
        self.assertEqual(len(worker._last_signal_time), 1)
        self.assertIn(("SH600000", "Daily:MACD底背离"), worker._last_signal_time)
        self.assertNotIn(("SZ000001", "Daily:RSI超卖"), worker._last_signal_time)

    def test_save_cache_on_stop_worker(self):
        """测试停止worker时保存缓存"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with (
            patch(
                "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
                self.cache_file,
            ),
            patch("stock_monitor.core.workers.quant_worker.CACHE_DIR", self.cache_dir),
        ):
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker = QuantWorker(mock_fetcher, "https://test.webhook")

            # 添加信号缓存
            now = time.time()
            worker._last_signal_time[("SH600000", "Daily:MACD底背离")] = now

            # 启动worker（设置_is_running为True）
            worker._is_running = True

            # 停止worker（应该保存缓存）
            with patch.object(worker, "wait"):
                worker.stop_worker()

            # 验证缓存已保存到文件
            self.assertTrue(self.cache_file.exists())

            with open(self.cache_file, encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("SH600000::Daily:MACD底背离", data)

    def test_cache_format_conversion(self):
        """测试tuple key和字符串格式的转换"""
        from stock_monitor.core.workers.quant_worker import QuantWorker

        mock_fetcher = MagicMock()
        mock_fetcher.mootdx_client = MagicMock()
        mock_fetcher.name_registry = MagicMock()

        with (
            patch(
                "stock_monitor.core.workers.quant_worker.SIGNAL_CACHE_FILE",
                self.cache_file,
            ),
            patch("stock_monitor.core.workers.quant_worker.CACHE_DIR", self.cache_dir),
        ):
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker1 = QuantWorker(mock_fetcher, "https://test.webhook")

            # 添加数据并保存
            now = time.time()
            test_key = ("SH600000", "Daily:MACD底背离")
            worker1._last_signal_time[test_key] = now
            worker1._save_signal_cache()

            # 加载和验证
            with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
                worker2 = QuantWorker(mock_fetcher, "https://test.webhook")

            # 验证数据被正确恢复
            self.assertIn(test_key, worker2._last_signal_time)
            self.assertEqual(worker2._last_signal_time[test_key], now)


if __name__ == "__main__":
    unittest.main()
