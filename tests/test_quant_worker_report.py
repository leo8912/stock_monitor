"""QuantWorker 后台复盘报告生成测试

验证 T07：手动复盘请求通过 ``QuantWorker.run_report`` 在后台上登记，
由后台线程消费（``_process_pending_report``）并发出 ``daily_report_ready``
信号，整个过程不阻塞调用方（UI）线程。
"""

import unittest
from unittest.mock import MagicMock, patch

from stock_monitor.core.workers.quant_worker import QuantWorker


class TestQuantWorkerReport(unittest.TestCase):
    """QuantWorker 后台报告生成测试"""

    def _make_worker(self) -> QuantWorker:
        fetcher = MagicMock()
        fetcher.market_adapter = MagicMock()
        fetcher.name_registry = MagicMock()
        with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
            return QuantWorker(fetcher, "https://test.webhook")

    def test_run_report_registers_pending(self):
        """run_report 只登记请求，不同步执行生成。"""
        worker = self._make_worker()
        worker.generate_daily_summary_report = MagicMock()

        self.assertIsNone(worker._pending_report_type)
        self.assertTrue(worker.run_report("manual"))

        # 仅登记，未执行
        self.assertEqual(worker._pending_report_type, "manual")
        worker.generate_daily_summary_report.assert_not_called()

    def test_process_pending_report_generates_and_emits(self):
        """消费请求时生成报告并发出 daily_report_ready 信号。"""
        worker = self._make_worker()
        called = []
        worker.generate_daily_summary_report = MagicMock(
            side_effect=lambda rt: called.append(rt)
        )
        emitted = []
        worker.daily_report_ready.connect(emitted.append)

        worker.run_report("manual")
        worker._process_pending_report()

        self.assertEqual(called, ["manual"])
        self.assertEqual(emitted, ["manual"])
        # 请求已被消费
        self.assertIsNone(worker._pending_report_type)

    def test_process_pending_report_noop_when_empty(self):
        """无待处理请求时不做任何事。"""
        worker = self._make_worker()
        worker.generate_daily_summary_report = MagicMock()

        worker._process_pending_report()

        worker.generate_daily_summary_report.assert_not_called()

    def test_process_pending_report_swallows_exception(self):
        """生成过程中抛异常不应外泄，也不发完成信号。"""
        worker = self._make_worker()
        worker.generate_daily_summary_report = MagicMock(
            side_effect=RuntimeError("boom")
        )
        emitted = []
        worker.daily_report_ready.connect(emitted.append)

        worker.run_report("manual")
        worker._process_pending_report()  # 不应抛出

        self.assertEqual(emitted, [])


if __name__ == "__main__":
    unittest.main()
