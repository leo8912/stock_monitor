"""
QuantWorker.run() 主循环与报告调度 characterization 测试

用 ``_stop_event`` 驱动有限次循环退出，锁定现有调度行为：
- 量化开关关闭时 5s 轮询、不扫描
- 开市时预热一次 + 按间隔扫描
- 定期存盘计数器逻辑
- 手动/定时复盘报告的登记-消费-去重
"""

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

CACHE_MODULE = "stock_monitor.core.workers.quant_worker"


def _make_worker():
    """创建依赖 mock 化的 QuantWorker。"""
    from stock_monitor.core.workers.quant_worker import QuantWorker

    mock_fetcher = MagicMock()
    mock_fetcher.market_adapter = MagicMock()
    mock_fetcher.name_registry = MagicMock()

    tmp = tempfile.TemporaryDirectory()
    tmp_dir = Path(tmp.name)
    try:
        with (
            patch(f"{CACHE_MODULE}.SIGNAL_CACHE_FILE", tmp_dir / "signal_cache.json"),
            patch(f"{CACHE_MODULE}.CACHE_DIR", tmp_dir),
            patch("stock_monitor.data.stock.stock_db.StockDatabase"),
        ):
            worker = QuantWorker(mock_fetcher, "https://test.webhook")
    except Exception:
        tmp.cleanup()
        raise
    worker.engine = MagicMock()
    worker.backtester = MagicMock()
    return worker, tmp


def _exit_after(worker, iterations: int, calls: list):
    """让 msleep 在指定次数后设置停止事件，使 run() 有限次迭代后退出。"""

    def fake_msleep(ms):
        calls.append(ms)
        if len(calls) >= iterations:
            worker._stop_event.set()

    worker.msleep = fake_msleep


class TestRunLoop(unittest.TestCase):
    def setUp(self):
        self.worker, self._tmp = _make_worker()
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        self._tmp.cleanup()

    def _patch_config(self, config: dict):
        from stock_monitor.core.config_center import config_center

        p = patch.object(config_center, "snapshot", return_value=config)
        p.start()
        self._patchers.append(p)

    def _patch_market(self, is_open: bool):
        mm = MagicMock()
        mm.is_market_open.return_value = is_open
        p = patch(
            "stock_monitor.core.market.market_manager.MarketManager",
            return_value=mm,
        )
        p.start()
        self._patchers.append(p)
        return mm

    def test_quant_disabled_sleeps_and_skips_scan(self):
        """量化开关关闭：5s 轮询、不预热、不扫描"""
        self.worker.symbols = ["sh600519"]
        self._patch_config({"quant_enabled": False})
        self._patch_market(is_open=True)

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
        ):
            self.worker.run()

        self.assertEqual(sleep_calls, [5000])
        mock_scan.assert_not_called()
        mock_warm.assert_not_called()

    def test_market_closed_no_scan_no_warm(self):
        """市场闭市：不预热、不扫描，但仍检查报告并以 1s 轮询"""
        self.worker.symbols = ["sh600519"]
        self._patch_config({"quant_enabled": True})
        self._patch_market(is_open=False)

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
            patch.object(self.worker, "check_and_trigger_reports") as mock_reports,
        ):
            self.worker.run()

        self.assertEqual(sleep_calls, [1000])
        mock_scan.assert_not_called()
        mock_warm.assert_not_called()
        mock_reports.assert_called_once()

    def test_market_open_warms_once_and_scans(self):
        """开市首轮：预热一次（15m/30m/60m/daily）+ 扫描 + 更新扫描时间"""
        self.worker.symbols = ["sh600519", "sz000001"]
        self._patch_config({"quant_enabled": True, "quant_scan_interval": 300})
        self._patch_market(is_open=True)

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
            patch.object(self.worker, "check_and_trigger_reports"),
            patch.object(self.worker, "_save_signal_cache") as mock_save,
        ):
            self.worker.run()

        mock_warm.assert_called_once()
        self.assertEqual(mock_warm.call_args.kwargs.get("categories"), [1, 2, 3, 9])
        self.assertEqual(mock_warm.call_args.kwargs.get("offset"), 100)
        self.assertTrue(self.worker._cache_warmed)
        mock_scan.assert_called_once()
        self.assertGreater(self.worker.last_scan_time, 0)
        # 存盘计数器为 1（< 10），未触发保存
        mock_save.assert_not_called()

    def test_warm_attempted_once_across_iterations(self):
        """预热只尝试一次：第二轮不再预热"""
        self.worker.symbols = ["sh600519"]
        self._patch_config({"quant_enabled": True})
        self._patch_market(is_open=True)

        sleep_calls = []
        _exit_after(self.worker, 2, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel"),
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
        ):
            self.worker.run()

        self.assertEqual(len(sleep_calls), 2)
        mock_warm.assert_called_once()

    def test_scan_skipped_within_interval(self):
        """距上次扫描不足间隔时不重复扫描"""
        self.worker.symbols = ["sh600519"]
        self._patch_config({"quant_enabled": True, "quant_scan_interval": 300})
        self._patch_market(is_open=True)
        self.worker.last_scan_time = time.time()  # 刚扫描过

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
        ):
            self.worker.run()

        mock_scan.assert_not_called()
        mock_warm.assert_called_once()  # 预热与扫描互相独立

    def test_warm_failure_does_not_break_loop(self):
        """预热异常被吞掉，扫描照常执行"""
        self.worker.symbols = ["sh600519"]
        self._patch_config({"quant_enabled": True})
        self._patch_market(is_open=True)

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer,
                "warm_cache_for_symbols",
                side_effect=RuntimeError("warm boom"),
            ),
        ):
            self.worker.run()  # 不应抛出

        mock_scan.assert_called_once()
        self.assertFalse(self.worker._cache_warmed)

    def test_empty_symbols_no_scan_no_warm(self):
        """无标的时不扫描、不预热（报告检查照常）"""
        self.worker.symbols = []
        self._patch_config({"quant_enabled": True})
        self._patch_market(is_open=True)

        sleep_calls = []
        _exit_after(self.worker, 1, sleep_calls)
        with (
            patch.object(self.worker, "perform_scan_parallel") as mock_scan,
            patch.object(
                self.worker.cache_warmer, "warm_cache_for_symbols"
            ) as mock_warm,
            patch.object(self.worker, "check_and_trigger_reports"),
        ):
            self.worker.run()

        mock_scan.assert_not_called()
        mock_warm.assert_not_called()

    def test_loop_survives_exception(self):
        """循环内异常被捕获，线程继续运行直至停止事件置位"""
        self._patch_config({"quant_enabled": True})
        self._patch_market(is_open=False)

        sleep_calls = []
        _exit_after(self.worker, 2, sleep_calls)
        with patch.object(
            self.worker, "check_and_trigger_reports", side_effect=RuntimeError("boom")
        ):
            self.worker.run()  # 不应抛出

        self.assertEqual(len(sleep_calls), 2)


class TestReportScheduling(unittest.TestCase):
    def setUp(self):
        self.worker, self._tmp = _make_worker()
        self.reports = []
        self.worker.daily_report_ready.connect(self.reports.append)

    def tearDown(self):
        self._tmp.cleanup()

    def _freeze_clock(self, hhmm: str):
        """把 check_and_trigger_reports 内的 datetime.now() 固定到指定时刻。"""
        from datetime import datetime as real_datetime

        fixed = real_datetime(2026, 9, 21, int(hhmm[:2]), int(hhmm[3:]))
        mock_dt = MagicMock()
        mock_dt.now.return_value = fixed
        return patch("datetime.datetime", mock_dt)

    def test_manual_report_via_pending_slot(self):
        """UI 登记 → 后台循环消费 → 生成 + 发信号 + 槽位清空"""
        self.assertTrue(self.worker.run_report("manual"))
        with patch.object(self.worker, "generate_daily_summary_report") as mock_gen:
            self.worker._process_pending_report()
            mock_gen.assert_called_once_with("manual")
        self.assertEqual(self.reports, ["manual"])
        # 槽位已消费，再次处理为空操作
        with patch.object(self.worker, "generate_daily_summary_report") as mock_gen:
            self.worker._process_pending_report()
            mock_gen.assert_not_called()

    def test_run_report_exception_caught(self):
        """报告生成异常不外泄，也不发完成信号"""
        self.worker.run_report("manual")
        with patch.object(
            self.worker,
            "generate_daily_summary_report",
            side_effect=RuntimeError("gen boom"),
        ):
            self.worker._process_pending_report()  # 不应抛出
        self.assertEqual(self.reports, [])

    def test_scheduled_morning_report(self):
        """11:35 触发早盘报告并记录去重标记"""
        self.worker._daily_report_times = ["11:35", "15:05"]
        clock = self._freeze_clock("11:35")
        with (
            clock,
            patch.object(self.worker, "generate_daily_summary_report") as mock_gen,
        ):
            self.worker.check_and_trigger_reports()
            mock_gen.assert_called_once_with("morning")
        self.assertEqual(self.reports, ["morning"])
        self.assertEqual(self.worker._last_report_date, "2026-09-21_morning")

    def test_report_times_read_from_config(self):
        """config['daily_report_times'] 优先于实例兜底值（配置键暴露）。"""
        self.worker._daily_report_times = ["11:35", "15:05"]
        self.worker.config = {"daily_report_times": ["09:45"]}
        clock = self._freeze_clock("09:45")
        with (
            clock,
            patch.object(self.worker, "generate_daily_summary_report") as mock_gen,
        ):
            self.worker.check_and_trigger_reports()
            mock_gen.assert_called_once_with("morning")
        self.assertEqual(self.reports, ["morning"])

    def test_report_times_empty_config_falls_back(self):
        """配置缺失/非列表时回落到实例兜底时刻。"""
        self.worker._daily_report_times = ["11:35"]
        self.worker.config = {"daily_report_times": []}
        clock = self._freeze_clock("11:35")
        with (
            clock,
            patch.object(self.worker, "generate_daily_summary_report") as mock_gen,
        ):
            self.worker.check_and_trigger_reports()
            mock_gen.assert_called_once_with("morning")

    def test_default_scan_interval_constant(self) -> None:
        """构造默认扫描间隔保持 5*60，未配置时不改变行为。"""
        from stock_monitor.core.workers.quant_worker import DEFAULT_SCAN_INTERVAL

        self.assertEqual(DEFAULT_SCAN_INTERVAL, 5 * 60)
        self.assertEqual(self.worker.scan_interval, 5 * 60)
        self.assertEqual(self.worker._daily_report_times, ["11:35", "15:05"])

    def test_scheduled_afternoon_report(self):
        """15:05 触发午盘报告"""
        self.worker._daily_report_times = ["11:35", "15:05"]
        clock = self._freeze_clock("15:05")
        with (
            clock,
            patch.object(self.worker, "generate_daily_summary_report") as mock_gen,
        ):
            self.worker.check_and_trigger_reports()
            mock_gen.assert_called_once_with("afternoon")
        self.assertEqual(self.reports, ["afternoon"])

    def test_scheduled_report_dedup(self):
        """同一天同一类型只触发一次"""
        self.worker._daily_report_times = ["11:35"]
        clock = self._freeze_clock("11:35")
        with (
            clock,
            patch.object(self.worker, "generate_daily_summary_report") as mock_gen,
        ):
            self.worker.check_and_trigger_reports()
            self.worker.check_and_trigger_reports()
            mock_gen.assert_called_once()
        self.assertEqual(self.reports, ["morning"])

    def test_scheduled_report_dedup_marker_blocks_any_trigger(self):
        """去重标记已设置时任何时刻都不再触发"""
        self.worker._last_report_date = "2099-01-01_morning"
        with patch.object(self.worker, "generate_daily_summary_report") as mock_gen:
            self.worker.check_and_trigger_reports()
            mock_gen.assert_not_called()
        self.assertEqual(self.reports, [])

    def test_scheduled_report_generation_error_caught(self):
        """定时报告生成异常不外泄、不发完成信号、不写去重标记（下轮可重试）"""
        self.worker._daily_report_times = ["11:35"]
        clock = self._freeze_clock("11:35")
        with (
            clock,
            patch.object(
                self.worker,
                "generate_daily_summary_report",
                side_effect=RuntimeError("gen boom"),
            ),
        ):
            self.worker.check_and_trigger_reports()  # 不应抛出
        self.assertEqual(self.reports, [])
        self.assertEqual(self.worker._last_report_date, "")  # 未标记，可重试


if __name__ == "__main__":
    unittest.main()
