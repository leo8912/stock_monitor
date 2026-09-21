"""
量化雷达扫描后台线程（并行优化版）
"""

from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger

# 缓存文件路径 (使用配置目录)
from ...config.manager import get_config_dir
from ...services.notifier import NotifierService
from ..cache.cache_warmer import CacheWarmer, PerformanceMonitor
from ..engine import WaveAnalyzer, WaveChart, quant_report, wave_report
from ..engine.backtest_engine import BacktestEngine
from ..engine.quant_engine import QuantEngine
from ..engine.quant_engine_constants import TF_CHINESE_MAP
from . import alert_text, scan_rules, signal_cache
from .base import DEFAULT_STOP_TIMEOUT_MS, wait_for_thread_stop

CACHE_DIR = Path(get_config_dir()) / "cache"
SIGNAL_CACHE_FILE = CACHE_DIR / "signal_cache.json"

# 常量定义
SIGNAL_CACHE_EXPIRY_SECONDS = 86400  # 信号缓存过期时间（24小时）
SIGNAL_CACHE_MAX_HISTORY_PER_SYMBOL = 100  # 每个符号最大历史记录数


class QuantWorker(QtCore.QThread):
    scan_started = QtCore.pyqtSignal()
    scan_finished = QtCore.pyqtSignal()
    # 后台复盘报告生成完成信号（emit: report_type，如 "manual"）
    daily_report_ready = QtCore.pyqtSignal(str)

    def __init__(
        self, stock_fetcher, wecom_webhook: str, scan_interval: int = 5 * 60
    ) -> None:
        super().__init__()
        self.fetcher = stock_fetcher
        self.engine = QuantEngine(self.fetcher.market_adapter)
        self.backtester = BacktestEngine(self.engine)
        self.notifier = NotifierService()
        self.wecom_webhook = wecom_webhook
        self.config = {}
        self.scan_interval = scan_interval
        self._stop_event = threading.Event()  # 使用Event替代bool标志
        self.last_scan_time = 0
        self.symbols: list[str] = []

        # 线程安全：使用锁保护共享资源
        self._lock = threading.Lock()
        self._alert_cache: set[str] = set()
        self._signal_manager: dict[str, float] = {}
        self._active_signals: dict[str, dict[str, dict]] = {}
        self._last_signal_time = {}  # 从磁盘加载持久化数据
        self._signals_history = {}
        self._daily_report_times = ["11:35", "15:05"]
        self._last_report_type = ""
        self._last_report_date = ""

        # 【新增】信号状态追踪：{(symbol, sig_name): {"last_score": int, "last_push_ts": float}}
        self._signal_states: dict[tuple[str, str], dict] = {}

        # 待处理的后台复盘报告请求（UI 线程非阻塞登记，由后台线程消费）
        self._pending_report_type: str | None = None

        # 性能优化：缓存预热器和性能监测
        self.cache_warmer = CacheWarmer(self.engine, self.fetcher, max_workers=4)
        self.perf_monitor = PerformanceMonitor()
        self._cache_warmed = False

        # 启动时加载持久化的信号缓存
        self._load_signal_cache()
        # 主循环存盘计数器（run() 每次启动时重置）
        self._save_cache_counter = 0

    def set_symbols(self, symbols: list[str]) -> None:
        """设置监控标的（G-11：存副本，避免与扫描线程共享同一 list 对象）。

        ``self.symbols`` 会被 ``run()`` 循环、线程池与报告生成并发迭代；若主线程
        直接改写同一 list 对象，会出现漏扫或 ``list changed size during
        iteration``。此处保存一份副本，读取统一走 :meth:`_symbols_snapshot`。
        """
        with self._lock:
            self.symbols = list(symbols)

    def _symbols_snapshot(self) -> list[str]:
        """返回当前监控标的的线程安全快照副本（G-11）。"""
        with self._lock:
            return list(self.symbols)

    def _load_signal_cache(self) -> None:
        """从磁盘加载信号缓存（防止重复告警）"""
        try:
            if not SIGNAL_CACHE_FILE.exists():
                app_logger.debug("信号缓存文件不存在，初始化新缓存")
                with self._lock:
                    self._last_signal_time = {}
                    self._signal_states = {}
                return

            with open(SIGNAL_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)

            # 在锁外解析，得到干净结果后一次性原子赋值
            last_signal_time, signal_states, expired_count = (
                signal_cache.parse_cache_payload(
                    data, time.time(), SIGNAL_CACHE_EXPIRY_SECONDS
                )
            )
            with self._lock:
                self._last_signal_time = last_signal_time
                self._signal_states = signal_states

            app_logger.info(
                f"加载信号缓存成功：{len(self._last_signal_time)} 个活跃信号，"
                f"已清理 {expired_count} 个过期项"
            )
        except Exception as e:
            app_logger.error(f"加载信号缓存失败：{e}，使用空缓存")
            with self._lock:
                self._last_signal_time = {}
                self._signal_states = {}

    def _save_signal_cache(self) -> None:
        """保存信号缓存到磁盘（G-12：临时文件 + os.replace 原子替换）。

        主线程与 worker 线程可能并发触发保存，直接以 ``"w"`` 打开目标文件会被
        读方（``_load_signal_cache``）读到半截内容。改为先写同目录临时文件，再
        通过 ``os.replace`` 原子替换，保证读方永远看到完整内容。
        """
        try:
            # 确保缓存目录存在
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # 使用锁获取信号状态的快照
            with self._lock:
                data = signal_cache.build_cache_payload(self._signal_states)

            signal_cache.atomic_write_json(SIGNAL_CACHE_FILE, data)

            app_logger.debug(f"信号缓存已保存：{len(data)} 个信号状态")
        except Exception as e:
            app_logger.error(f"保存信号缓存失败：{e}")

    def start_worker(self) -> None:
        """启动量化扫描线程（清空停止标志，已在运行时跳过）。"""
        if self.isRunning():
            app_logger.warning("QuantWorker 线程仍在运行，跳过启动")
            return

        # stop_worker() 会设置该事件；重新启用量化功能时必须清除它，
        # 否则 run() 会立即退出，导致同一会话内无法恢复扫描。
        self._stop_event.clear()
        self.start()

    def stop_worker(self) -> None:
        """停止量化线程（轮询等待线程真正结束）。

        注意：**不关闭数据库连接池**。``StockDatabase`` 为单例，其连接池由应用
        退出流程（``MainWindow._shutdown_resources``）统一关闭；在此关闭会让其它
        线程的查询报 "Cannot operate on a closed database"。
        """
        self._stop_event.set()
        self.requestInterruption()
        # 停止前保存信号缓存，防止重启后出现重复告警
        self._save_signal_cache()
        if not wait_for_thread_stop(self):
            app_logger.warning(
                f"QuantWorker 停止超时（>{DEFAULT_STOP_TIMEOUT_MS}ms），线程可能仍在收尾"
            )

    def run_report(self, report_type: str = "manual") -> bool:
        """登记一次后台复盘报告生成请求（非阻塞，供 UI 线程调用）。

        请求会被放入待处理槽位，由后台 ``run()`` 循环在自身线程内消费并调用
        :meth:`generate_daily_summary_report`，完成后发出
        :attr:`daily_report_ready` 信号。这样可避免在 UI 线程同步执行耗时的
        全量复盘分析（网络请求 + 指标计算）导致界面卡死。

        Args:
            report_type: 报告类型（"manual" / "auto" 等）。

        Returns:
            是否成功登记请求。
        """
        with self._lock:
            self._pending_report_type = report_type
        app_logger.info_ctx("已登记后台复盘报告请求", report_type=report_type)
        return True

    def check_and_trigger_reports(self) -> None:
        """检查并触发定时报告生成（早盘/午盘复盘）"""
        try:
            from datetime import datetime

            now = datetime.now()
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            # 检查是否需要生成定时报告
            if current_time in self._daily_report_times:
                # 避免同一天重复生成
                report_type = "morning" if current_time == "11:35" else "afternoon"
                report_key = f"{today}_{report_type}"

                if self._last_report_date != report_key:
                    app_logger.info(f"触发定时报告生成：{report_type}")
                    self.generate_daily_summary_report(report_type)
                    self.daily_report_ready.emit(report_type)
                    self._last_report_date = report_key
                    self._last_report_type = report_type
        except Exception as e:
            app_logger.error(f"检查报告生成失败：{e}")

    def _process_pending_report(self) -> None:
        """在后台线程内消费 UI 登记的复盘报告请求（非阻塞）。"""
        with self._lock:
            report_type = self._pending_report_type
            self._pending_report_type = None
        if not report_type:
            return
        self._run_report(report_type)

    def _run_report(self, report_type: str) -> None:
        """在后台线程内生成复盘报告并发出完成信号（异常不外泄）。"""
        try:
            self.generate_daily_summary_report(report_type)
            self.daily_report_ready.emit(report_type)
        except Exception as e:
            app_logger.error(f"后台复盘报告生成失败：{e}")

    def _analyze_symbol_waves(
        self, symbol: str, daily_df
    ) -> tuple[dict | None, dict | None]:
        """分析单只股票的日线与 60 分钟波浪，返回 (日线浪, 60m浪)。

        Args:
            symbol: 股票代码（如 sh600000）。
            daily_df: 日线 K 线数据。

        Returns:
            (daily_wave, h60_wave)：波浪结果字典，分析失败为 None。
        """
        daily_wave = None
        h60_wave = None
        try:
            h60_df = self.engine.fetch_bars(symbol, category=3, offset=100)
            daily_res = WaveAnalyzer.analyze(daily_df)
            h60_res = WaveAnalyzer.analyze(h60_df)
            if daily_res:
                daily_wave = daily_res.current_wave
            if h60_res:
                h60_wave = h60_res.current_wave
        except Exception as wave_err:
            app_logger.warning(f"复盘报告分析波浪异常 ({symbol}): {wave_err}")
        return daily_wave, h60_wave

    def _analyze_symbol_for_report(self, symbol: str) -> dict | None:
        """扫描单只自选股并汇总信号，数据不足/无信号/异常时返回 None。

        Args:
            symbol: 股票代码（如 sh600000）。

        Returns:
            信号信息字典（含评分、审计、波浪等）；否则 None。
        """
        try:
            stock_name = self.fetcher.name_registry.get_name(symbol)
            code, market, _ = self.engine._parse_symbol(symbol)

            # 获取最新价格和 K 线
            p_info = self.engine.get_latest_price_info(symbol)
            daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)

            if daily_df.empty or len(daily_df) < 50:
                return None

            # 执行技术面分析
            signals = self.engine.scan_all_timeframes(symbol)

            # OBV 累积检测
            obv_signals = self.engine.detect_obv_accumulation(symbol, daily_df)
            signals.extend(obv_signals)

            # 波浪与斐波那契分析 (日线 + 60m)
            daily_wave, h60_wave = self._analyze_symbol_waves(symbol, daily_df)

            if not signals:
                return None

            # 计算强度评分
            score, audit = self.engine.calculate_intensity_score_with_symbol(
                symbol, daily_df, signals
            )

            return {
                "symbol": symbol,
                "name": stock_name,
                "signals": [s["name"] for s in signals],
                "score": score,
                "audit": audit,
                "price": p_info.get("price", 0),
                "pct": p_info.get("pct", 0),
                "wave_daily": daily_wave,
                "wave_60m": h60_wave,
            }
        except Exception as e:
            app_logger.error(f"扫描 {symbol} 失败：{e}")
            return None

    def _collect_report_signals(
        self, symbols: list[str]
    ) -> tuple[list[dict], list[dict]]:
        """遍历自选股收集全部信号与高分信号。

        Args:
            symbols: 自选股代码列表。

        Returns:
            (all_signals, strong_signals)：全部信号与评分 >= 3 的信号。
        """
        all_signals: list[dict] = []
        strong_signals: list[dict] = []
        for symbol in symbols:
            signal_info = self._analyze_symbol_for_report(symbol)
            if signal_info is None:
                continue
            all_signals.append(signal_info)
            # 高分信号单独标记
            if signal_info["score"] >= 3:
                strong_signals.append(signal_info)
        return all_signals, strong_signals

    def _webhook_override(self, report_type: str):
        """手动复盘使用自定义企微 webhook，其余情况走默认配置。"""
        return self.wecom_webhook if report_type == "manual" else None

    def _push_symbol_wave_text(
        self, report_type: str, symbol: str, stock_name: str
    ) -> None:
        """为单只股票推送日线与 60 分钟波浪文字分析。"""
        try:
            daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)
            h60_df = self.engine.fetch_bars(symbol, category=3, offset=100)

            # 日线波浪分析与文字推送
            if daily_df is not None and not daily_df.empty:
                daily_text = self._format_wave_text_analysis(
                    symbol, stock_name, "日线", daily_df
                )
                if daily_text:
                    NotifierService.dispatch_custom_message(
                        config=self.config,
                        title=f"📊 波浪形态复盘: {stock_name} (日线)",
                        content=daily_text,
                        webhook_override=self._webhook_override(report_type),
                    )
                    time.sleep(0.5)

            # 60m波浪分析与文字推送
            if h60_df is not None and not h60_df.empty:
                h60_text = self._format_wave_text_analysis(
                    symbol, stock_name, "60分钟线", h60_df
                )
                if h60_text:
                    NotifierService.dispatch_custom_message(
                        config=self.config,
                        title=f"📊 波浪形态复盘: {stock_name} (60m)",
                        content=h60_text,
                        webhook_override=self._webhook_override(report_type),
                    )
                    time.sleep(0.5)
        except Exception as wave_err:
            app_logger.error(f"为复盘生成推送波浪文字分析失败 ({symbol}): {wave_err}")

    def _send_report_and_wave_text(
        self,
        report_type: str,
        report_title: str,
        report_content: str,
        all_signals: list[dict],
    ) -> None:
        """发送文字版复盘报告，并为信号最强的 5 只股票补推波浪文字分析。"""
        NotifierService.dispatch_custom_message(
            config=self.config,
            title=report_title,
            content=report_content,
            webhook_override=self._webhook_override(report_type),
        )
        app_logger.info(f"复盘报告已发送：{report_title}，共 {len(all_signals)} 个信号")

        # 为前 5 个信号最佳的股票生成并推送详细的波浪与斐波那契文字分析
        for sig in all_signals[:5]:
            self._push_symbol_wave_text(report_type, sig["symbol"], sig["name"])

    def _auto_export_stocks(self, symbols: list[str]) -> None:
        """收盘/定时复盘时按配置自动导出自选股 Excel 报表。"""
        if not self.config.get("auto_export_excel", False):
            return
        app_logger.info("自动导出配置已启用，正在生成自选股 Excel 报表...")
        try:
            from scripts.reporting.export_stocks_to_excel import export_to_excel

            export_to_excel(
                output_path="analysis_reports/stock_export_report.xlsx",
                include_history=True,
                history_symbols=symbols,
            )
            app_logger.info("自选股 Excel 报表自动导出成功！")
        except Exception as ex:
            app_logger.error(f"自选股 Excel 报表自动导出失败：{ex}")

    def generate_daily_summary_report(self, report_type: str = "auto") -> None:
        """生成每日复盘报告

        Args:
            report_type: 报告类型 ("morning", "afternoon", "manual", "auto")
        """
        # G-11：报告生成耗时较长，使用标的快照，避免与主线程替换并发
        symbols = self._symbols_snapshot()

        try:
            if not symbols:
                app_logger.warning("无自选股，跳过报告生成")
                return

            app_logger.info(
                f"开始生成 {report_type} 复盘报告，扫描 {len(symbols)} 只股票..."
            )

            # 收集所有信号
            all_signals, strong_signals = self._collect_report_signals(symbols)

            # 生成报告内容
            report_title = self._get_report_title(report_type)
            report_content = self._format_report_content(
                report_title, all_signals, strong_signals, report_type
            )

            # 发送报告
            if report_content and self.config:
                self._send_report_and_wave_text(
                    report_type, report_title, report_content, all_signals
                )

            # 自动导出自选股数据到 Excel (在收盘/定时复盘时触发)
            self._auto_export_stocks(symbols)

        except Exception as e:
            app_logger.error(f"生成复盘报告失败：{e}")

    def _get_prev_next_wave(self, wave: str) -> tuple[str, str]:
        """获取前一浪和预计下一浪"""
        return wave_report.get_prev_next_wave(wave)

    def _analyze_major_and_sub_waves(self, df):
        """先按粗阈值寻找大浪结构，再以细阈值分析子浪，返回 (大浪, 子浪)。"""
        return wave_report.analyze_major_and_sub_waves(df)

    @staticmethod
    def _resolve_sub_wave(sub_res) -> tuple[str, str]:
        """从子浪分析结果解析浪型标识与说明，无结果时返回空串。"""
        return wave_report.resolve_sub_wave(sub_res)

    @staticmethod
    def _build_fib_support_resistance(
        levels: dict, curr_price: float
    ) -> tuple[str, str]:
        """根据斐波那契位与当前价拆分支撑位与阻力位字符串。"""
        return wave_report.build_fib_support_resistance(levels, curr_price)

    @staticmethod
    def _format_wave_history_lines(all_waves: list[dict]) -> list[str]:
        """格式化历史波段（时间 + 空间）文本行，含当前位置标记。"""
        return wave_report.format_wave_history_lines(all_waves)

    @staticmethod
    def _format_remaining_space_lines(rs: dict) -> list[str]:
        """格式化剩余空间预估（目标位 / 空间 / 预计天数）文本行。"""
        return wave_report.format_remaining_space_lines(rs)

    def _format_wave_text_analysis(
        self, symbol: str, name: str, timeframe_name: str, df
    ) -> str:
        """将波浪分析结果格式化为简洁易懂的文本卡片"""
        return wave_report.format_wave_text_analysis(symbol, name, timeframe_name, df)

    @staticmethod
    def _explain_wave(wave: str, trend: str | None) -> str:
        """用通俗语言解释当前浪型含义"""
        return wave_report.explain_wave(wave, trend)

    @staticmethod
    def _wave_action_hint(wave: str, trend: str | None) -> str:
        """给出简洁的操作建议"""
        return wave_report.wave_action_hint(wave, trend)

    def _get_report_title(self, report_type: str) -> str:
        """获取报告标题"""
        return quant_report.get_report_title(report_type)

    def _format_report_content(
        self, title: str, all_signals: list, strong_signals: list, report_type: str
    ) -> str:
        """格式化报告内容（使用 Markdown 格式）"""
        return quant_report.format_report_content(
            title, all_signals, strong_signals, report_type
        )

    def run(self) -> None:
        """量化雷达线程主循环。

        每轮迭代委托 :meth:`_run_iteration`；量化开关关闭时该迭代仅做 5s
        等待并跳过底部的 1s 轮询（保持原 ``continue`` 语义）。
        """
        app_logger.info_ctx("量化雷达侦测线程已启动", action="start")
        # 每 10 次循环保存一次缓存（每次 run() 重新计数）
        self._save_cache_counter = 0

        # 首次运行时进行缓存预热
        cache_warming_attempted = False

        while not self._stop_event.is_set():
            try:
                cache_warming_attempted, fast_poll = self._run_iteration(
                    cache_warming_attempted
                )
                if fast_poll:
                    continue
            except Exception as e:
                app_logger.error(f"QuantWorker 运行异常：{e}")
            self.msleep(1000)

    def _run_iteration(self, cache_warming_attempted: bool) -> tuple[bool, bool]:
        """执行一次主循环迭代。

        Args:
            cache_warming_attempted: 跨迭代的"本轮 run 是否已尝试预热"标记。

        Returns:
            (cache_warming_attempted, fast_poll)：``fast_poll`` 为 True 表示
            量化开关关闭，调用方应跳过底部 1s 轮询（迭代内已等待 5s）。
        """
        from stock_monitor.core.config_center import config_center

        from ..market.market_manager import MarketManager

        # 优先处理 UI 登记的手动报告请求（不依赖量化开关，避免阻塞 UI）
        self._process_pending_report()

        self.config = config_center.snapshot()
        if not self.config.get("quant_enabled", False):
            self.msleep(5000)
            return cache_warming_attempted, True

        # G-11：本轮循环使用标的快照，避免主线程并发替换
        symbols_snapshot = self._symbols_snapshot()

        # 在第一次进入市场开盘时进行缓存预热
        if MarketManager().is_market_open() and not cache_warming_attempted:
            cache_warming_attempted = True
            if symbols_snapshot and not self._cache_warmed:
                app_logger.info("触发缓存预热...")
                try:
                    self.cache_warmer.warm_cache_for_symbols(
                        symbols_snapshot,
                        categories=[1, 2, 3, 9],  # 15m, 30m, 60m, daily
                        offset=100,
                    )
                    self._cache_warmed = True
                except Exception as e:
                    app_logger.error(f"缓存预热失败：{e}")

        if MarketManager().is_market_open():
            current_interval = self.config.get(
                "quant_scan_interval", self.scan_interval
            )
            if (
                symbols_snapshot
                and time.time() - self.last_scan_time >= current_interval
            ):
                scan_start = time.time()
                self.perform_scan_parallel()
                scan_duration = time.time() - scan_start
                self.perf_monitor.record_scan_time(scan_duration)
                self.last_scan_time = time.time()
                app_logger.info_ctx(
                    "量化扫描完成",
                    symbols=len(symbols_snapshot),
                    duration_ms=f"{scan_duration * 1000:.0f}",
                )

        self.check_and_trigger_reports()

        # 定期保存信号缓存（每10次循环保存一次，避免过于频繁的磁盘I/O）
        self._save_cache_counter += 1
        if self._save_cache_counter >= 10:
            self._save_signal_cache()
            self._save_cache_counter = 0

        return cache_warming_attempted, False

    def perform_scan(self) -> None:
        """对全部自选股执行批量量化扫描（串行兼容入口，委托并行版本执行）"""
        # 直接委托并行版本，线程池大小由配置决定
        # 保留此方法以兼容外部调用
        self.perform_scan_parallel()

    def perform_scan_parallel(self) -> None:
        """并行量化扫描（ThreadPoolExecutor 优化版）"""
        self.scan_started.emit()

        # G-11：使用标的快照，避免主线程并发替换导致漏扫/迭代异常
        symbols = self._symbols_snapshot()
        app_logger.info(f"开始并行量化扫描，监控标的：{len(symbols)} 只")

        if not symbols:
            self.scan_finished.emit()
            return

        # 从配置读取线程池大小限制，带安全边界
        # 默认：min(CPU核心数, 符号数, 16)
        # 范围：[2, 32]
        max_workers = self.config.get("quant_max_workers", None)
        if max_workers is None:
            # 自动推荐：CPU核心数默认为4-8，但不超过16
            import os

            cpu_count = os.cpu_count() or 4
            max_workers = min(cpu_count, 16)
        else:
            max_workers = int(max_workers)

        # 应用安全边界
        max_workers = min(max(max_workers, 2), 32)  # 至少2线程，最多32线程
        max_workers = min(max_workers, len(symbols))  # 不超过符号数

        results = []

        app_logger.info(
            f"使用 {max_workers} 个线程扫描（配置: {self.config.get('quant_max_workers', '自动')}, 建议: CPU核心优化）"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有扫描任务
            futures = {
                executor.submit(self._scan_single_symbol, symbol): symbol
                for symbol in symbols
            }

            # 收集结果，带超时保护（避免长期阻塞）
            for future in as_completed(futures, timeout=120):
                symbol = futures[future]
                try:
                    result = future.result(timeout=30)
                    if result:
                        results.append(result)
                except Exception as e:
                    app_logger.error(f"标的 {symbol} 扫描失败：{e}")

        self.scan_finished.emit()
        app_logger.info(f"本轮量化扫描完毕，触发信号：{len(results)} 次")

    def _scan_single_symbol(self, symbol: str) -> dict:
        """扫描单只股票（供线程池调用）

        数据获取依赖 engine/backtester，决策规则见 scan_rules 纯函数模块。
        """
        try:
            stock_name = self.fetcher.name_registry.get_name(symbol)
            code, market, _ = self.engine._parse_symbol(symbol)

            p_info = self.engine.get_latest_price_info(symbol)
            daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)

            signals = self.engine.scan_all_timeframes(symbol)

            obv_signals = self.engine.detect_obv_accumulation(symbol, daily_df)
            scan_rules.append_obv_signals(signals, obv_signals)

            daily_stats = self.backtester.get_strategy_stats(code, market, category=9)

            rsrs_z, _ = self.engine.calculate_rsrs(daily_df)
            is_confluence = scan_rules.is_confluence(signals, rsrs_z)

            is_priority, _wr_label = scan_rules.is_priority_symbol(daily_stats)

            score, audit = self.engine.calculate_intensity_score_with_symbol(
                symbol, daily_df, signals
            )

            threshold = 2 if is_priority else 3

            if is_confluence:
                signals, score = scan_rules.apply_confluence(signals, score)

            scan_rules.append_multi_factor_fallback(
                signals, score, threshold, _wr_label
            )

            if signals:
                return self._process_signals(
                    symbol,
                    stock_name,
                    signals,
                    score,
                    audit,
                    p_info,
                    is_priority,
                    is_confluence,
                    daily_df,
                )

        except Exception as e:
            app_logger.error(f"标的 {symbol} 扫描异常：{e}")

        return None

    def _should_push_signal(
        self, symbol: str, sig_name: str, current_score: int
    ) -> tuple[bool, str]:
        """
        判断是否应该推送信号（防抖动核心逻辑）

        Returns:
            (should_push, reason): 是否推送及原因
        """
        now = time.time()
        state_key = (symbol, sig_name)

        # 1. 获取配置参数
        cooldown = self.config.get("quant_alert_cooldown", 1800)  # 默认30分钟
        score_threshold = self.config.get("quant_alert_score_threshold", 2)

        with self._lock:
            # 2. 首次出现或缓存缺失 → 允许推送
            if state_key not in self._signal_states:
                return True, "新信号"

            state = self._signal_states[state_key]
            last_push_ts = state.get("last_push_ts", 0)
            last_score = state.get("last_score", -999)

            # 3. 冷却时间检查
            elapsed = now - last_push_ts
            if elapsed < cooldown:
                # 4. 冷却期内：只有评分显著变化才重新推送
                score_diff = abs(current_score - last_score)
                if score_diff >= score_threshold:
                    return True, f"评分显著变化 ({last_score:+}→{current_score:+})"
                else:
                    return False, f"冷却中 (剩余{int(cooldown - elapsed)}s)"

        # 5. 超过冷却时间 → 允许推送
        return True, "冷却结束"

    def _update_signal_state(self, symbol: str, sig_name: str, score: int) -> None:
        """更新信号状态记录"""
        state_key = (symbol, sig_name)
        with self._lock:
            self._signal_states[state_key] = {
                "last_score": score,
                "last_push_ts": time.time(),
            }

    def _merge_signals_for_symbol(
        self, symbol: str, stock_name: str, signals_data: list[dict]
    ) -> dict:
        """
        将同一股票的多个信号合并为一条精简推送

        Args:
            symbol: 股票代码
            stock_name: 股票名称
            signals_data: 信号列表 [{sig_name, score, audit, p_info, ...}]

        Returns:
            合并后的推送数据
        """
        if not signals_data:
            return None

        # 历史轨迹（取快照后由纯函数构建文案）
        with self._lock:
            history_list = list(self._signals_history.get(symbol, []))

        return alert_text.merge_signals_text(
            symbol, stock_name, signals_data, history_list
        )

    def _collect_pending_signals(
        self, symbol, signals, score, audit, p_info, is_priority, is_confluence
    ) -> list[dict]:
        """对原始信号做防抖动过滤，返回允许推送的信号列表。"""
        pending_signals = []
        for sig in signals:
            tf_cn = TF_CHINESE_MAP.get(sig.get("tf", "Daily"), "日线")
            sig_name = f"{tf_cn}:{sig['name']}"

            # 防抖动检测
            should_push, reason = self._should_push_signal(symbol, sig_name, score)

            if should_push:
                pending_signals.append(
                    {
                        "sig": sig,
                        "sig_name": sig_name,
                        "score": score,
                        "audit": audit,
                        "p_info": p_info,
                        "is_priority": is_priority,
                        "is_confluence": is_confluence,
                        "reason": reason,
                    }
                )
                app_logger.debug(f"[{symbol}] {sig_name} 允许推送: {reason}")
            else:
                app_logger.debug(f"[{symbol}] {sig_name} 跳过: {reason}")
        return pending_signals

    def _analyze_waves_for_signal(self, symbol, cached_daily_df=None):
        """分析日线与 60m 波浪，返回 (日线文本, 60m文本, 日线结果, 60m结果)。"""
        daily_wave_text = ""
        h60_wave_text = ""
        daily_res = None
        h60_res = None
        try:
            daily_df = (
                cached_daily_df
                if cached_daily_df is not None
                else self.engine.fetch_bars(symbol, category=9, offset=100)
            )
            h60_df = self.engine.fetch_bars(symbol, category=3, offset=100)
            daily_res = WaveAnalyzer.analyze(daily_df)
            h60_res = WaveAnalyzer.analyze(h60_df)
            if daily_res:
                daily_wave_text = f"\n🌊 **波浪定位(日线)**：{daily_res.current_wave.get('desc', '判断中')} (第 {daily_res.current_wave.get('wave', '')} 浪)"
            if h60_res:
                h60_wave_text = f"\n🌊 **波浪定位(60m)**：{h60_res.current_wave.get('desc', '判断中')} (第 {h60_res.current_wave.get('wave', '')} 浪)"
        except Exception as wave_err:
            app_logger.warning(f"即时扫描分析波浪异常 ({symbol}): {wave_err}")
        return daily_wave_text, h60_wave_text, daily_res, h60_res

    def _push_merged_signals(
        self, symbol, stock_name, pending_signals, daily_wave_text, h60_wave_text
    ) -> list[str]:
        """合并推送模式：一次推送该股票的全部信号，返回已触发的信号名。"""
        triggered = []
        merged = self._merge_signals_for_symbol(symbol, stock_name, pending_signals)
        if merged:
            # 注入波浪文本
            merged["cycle_info"] += f"\n{daily_wave_text}{h60_wave_text}"
            NotifierService.dispatch_alert(
                config=self.config,
                symbol=symbol,
                stock_name=merged["title"].replace(f" ({symbol})", ""),
                signals=[merged["signals_text"]],
                cycle_info=merged["cycle_info"],
                price_info=merged["p_info"],
            )
            app_logger.info(f"发送合并推送：{symbol} ({len(pending_signals)}个信号)")

            # 更新所有信号的状态
            for ps in pending_signals:
                self._update_signal_state(symbol, ps["sig_name"], ps["score"])
                triggered.append(ps["sig_name"])
        return triggered

    def _build_backtest_stats_text(self, symbol, ps) -> str:
        """按门槛获取同类信号回测统计并格式化为推送文案，无数据返回空串。"""
        min_backtest_score = 3 if ps["score"] >= 3 else 1
        stats = self.backtester.get_score_stats(
            symbol,
            1 if symbol.startswith("sh") else 0,
            min_score=min_backtest_score,
        )
        return alert_text.format_backtest_stats(stats)

    def _build_display_labels(self, stock_name, ps) -> tuple[str, str]:
        """构建带优先级/共振标记的展示名称与信号后缀。"""
        return alert_text.build_display_labels(
            stock_name, ps["is_priority"], ps["is_confluence"]
        )

    def _build_individual_cycle_info(
        self, symbol, stock_name, ps, daily_wave_text, h60_wave_text
    ) -> dict:
        """构建单个信号的推送文案（含 Alpha、回测胜率、财务审计与今日轨迹）。"""
        benchmark_pct, is_valid = self.engine.get_market_relative_strength()
        if not is_valid:
            app_logger.warning(f"[{symbol}] 大盘数据获取失败，Alpha 计算可能不准确")
        alpha = ps["p_info"].get("pct", 0.0) - benchmark_pct

        stats_text = self._build_backtest_stats_text(symbol, ps)

        fin_label = ps["audit"].get("label", "[财务稳健]")
        fin_reasons = " / ".join(ps["audit"].get("reasons", []))
        fin_info = f"{fin_label} {fin_reasons if fin_reasons else ''}"

        display_name, display_sig = self._build_display_labels(stock_name, ps)

        cycle_info = f"信号详情：{ps['sig_name']}\n\n"
        cycle_info += f"🚀 **超值强度**：{ps['score']:+}分 (Alpha: {alpha:+.2f}%)\n\n"
        cycle_info += f"🏥 **财务审计**：{fin_info}\n"
        # 注入波浪文本
        cycle_info += f"{daily_wave_text}\n{h60_wave_text}\n"
        cycle_info += stats_text

        with self._lock:
            history_list = self._signals_history.get(symbol, [])
        cycle_info += alert_text.format_history_text(history_list)

        return {
            "display_name": display_name,
            "display_sig": display_sig,
            "fin_info": fin_info,
            "cycle_info": cycle_info,
        }

    def _push_individual_signals(
        self, symbol, stock_name, pending_signals, daily_wave_text, h60_wave_text
    ) -> list[str]:
        """单独推送模式：为每个信号分别构建并发送推送，返回已触发的信号名。"""
        triggered = []
        for ps in pending_signals:
            info = self._build_individual_cycle_info(
                symbol, stock_name, ps, daily_wave_text, h60_wave_text
            )
            NotifierService.dispatch_alert(
                config=self.config,
                symbol=symbol,
                stock_name=info["display_name"],
                signals=[
                    f"{ps['sig_name']}{info['display_sig']} [评分：{ps['score']:+}分]",
                    info["fin_info"],
                ],
                cycle_info=info["cycle_info"],
                price_info=ps["p_info"],
            )
            app_logger.info(
                f"发送量化异动即时推送：{stock_name} ({ps['sig_name']}) [{ps['reason']}]"
            )

            # 更新状态
            self._update_signal_state(symbol, ps["sig_name"], ps["score"])
            triggered.append(ps["sig_name"])
        return triggered

    def _push_single_wave_chart(
        self, symbol, stock_name, res, timeframe, label
    ) -> None:
        """生成单张波浪分析图并推送，随后删除临时图片。"""
        img = WaveChart.generate(res, symbol, stock_name, timeframe=timeframe)
        if not (img and os.path.exists(img)):
            return
        NotifierService.dispatch_image(
            config=self.config,
            image_path=img,
            title=f"【异动图表】{stock_name} ({symbol}) {label}\n当前位置: {res.current_wave.get('desc', '')}",
        )
        try:
            os.remove(img)
        except OSError as e:
            app_logger.debug(f"删除临时图片失败: {e}")

    def _push_wave_charts(self, symbol, stock_name, daily_res, h60_res) -> None:
        """统一生成并推送波浪分析 K 线图（日线 + 60m）。"""
        try:
            if daily_res:
                self._push_single_wave_chart(
                    symbol, stock_name, daily_res, "daily", "日线波浪形态"
                )
            if h60_res:
                self._push_single_wave_chart(
                    symbol, stock_name, h60_res, "60m", "60分钟波浪形态"
                )
        except Exception as img_err:
            app_logger.error(f"即时扫描推送波浪图表失败 ({symbol}): {img_err}")

    def _record_signal_history(self, symbol, pending_signals, current_time_str) -> None:
        """记录本次推送的今日轨迹，并裁剪历史长度防止内存泄漏。"""
        with self._lock:
            if symbol not in self._signals_history:
                self._signals_history[symbol] = []
            for ps in pending_signals:
                self._signals_history[symbol].append(
                    {
                        "time": current_time_str,
                        "name": ps["sig_name"],
                        "score": ps["score"],
                    }
                )
            # 限制历史记录数量
            if len(self._signals_history[symbol]) > SIGNAL_CACHE_MAX_HISTORY_PER_SYMBOL:
                self._signals_history[symbol] = self._signals_history[symbol][
                    -SIGNAL_CACHE_MAX_HISTORY_PER_SYMBOL:
                ]

    def _process_signals(
        self,
        symbol,
        stock_name,
        signals,
        score,
        audit,
        p_info,
        is_priority,
        is_confluence,
        cached_daily_df=None,
    ) -> dict:
        """
        处理并发送信号（优化版：防抖动 + 信号合并 + 强度门槛）
        """
        # 【新增】强度门槛检查：防止低分信号频繁打扰
        min_push_score = self.config.get("quant_min_push_score", 2)
        if score < min_push_score and not is_confluence:
            app_logger.debug(
                f"[{symbol}] 评分 {score} 低于推送门槛 {min_push_score}，已拦截"
            )
            return None

        current_time_str = time.strftime("%H:%M")
        merge_enabled = self.config.get("quant_alert_merge_enabled", True)

        # 【阶段1】收集所有待推送信号
        pending_signals = self._collect_pending_signals(
            symbol, signals, score, audit, p_info, is_priority, is_confluence
        )
        if not pending_signals:
            return None

        # 1. 运行波浪定位分析
        daily_wave_text, h60_wave_text, daily_res, h60_res = (
            self._analyze_waves_for_signal(symbol, cached_daily_df)
        )

        # 【阶段2】根据配置决定是合并推送还是单独推送
        if merge_enabled and len(pending_signals) > 1:
            triggered = self._push_merged_signals(
                symbol, stock_name, pending_signals, daily_wave_text, h60_wave_text
            )
        else:
            triggered = self._push_individual_signals(
                symbol, stock_name, pending_signals, daily_wave_text, h60_wave_text
            )

        # 3. 统一生成并推送波浪分析 K 线图
        self._push_wave_charts(symbol, stock_name, daily_res, h60_res)

        # 记录历史轨迹（限制每个符号历史记录数量，防止内存泄漏）
        self._record_signal_history(symbol, pending_signals, current_time_str)

        return {"symbol": symbol, "signals": triggered}
