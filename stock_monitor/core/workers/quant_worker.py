"""
量化雷达扫描后台线程（并行优化版）
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger

from ...services.notifier import NotifierService
from ..backtest_engine import BacktestEngine
from ..cache_warmer import CacheWarmer, PerformanceMonitor
from ..quant_engine import QuantEngine

# 缓存文件路径 (与应用日志同目录)
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
SIGNAL_CACHE_FILE = CACHE_DIR / "signal_cache.json"


class QuantWorker(QtCore.QThread):
    scan_started = QtCore.pyqtSignal()
    scan_finished = QtCore.pyqtSignal()

    def __init__(self, stock_fetcher, wecom_webhook: str, scan_interval: int = 5 * 60):
        super().__init__()
        self.fetcher = stock_fetcher
        self.engine = QuantEngine(self.fetcher.mootdx_client)
        self.backtester = BacktestEngine(self.engine)
        self.notifier = NotifierService()
        self.wecom_webhook = wecom_webhook
        self.config = {}
        self.scan_interval = scan_interval
        self._is_running = False
        self.last_scan_time = 0
        self.symbols: list[str] = []
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

        # 性能优化：缓存预热器和性能监测
        self.cache_warmer = CacheWarmer(self.engine, self.fetcher, max_workers=4)
        self.perf_monitor = PerformanceMonitor()
        self._cache_warmed = False

        from ...data.stock.stock_db import StockDatabase

        self.db = StockDatabase()

        # 启动时加载持久化的信号缓存
        self._load_signal_cache()

    def set_symbols(self, symbols: list[str]):
        self.symbols = symbols

    def _load_signal_cache(self):
        """从磁盘加载信号缓存（防止重复告警）"""
        try:
            if not SIGNAL_CACHE_FILE.exists():
                app_logger.debug("信号缓存文件不存在，初始化新缓存")
                self._last_signal_time = {}
                self._signal_states = {}
                return

            with open(SIGNAL_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)

            # 恢复_last_signal_time dict，需要转换key回tuple格式
            self._last_signal_time = {}
            self._signal_states = {}

            for key_str, value in data.items():
                # key_str 格式: "symbol::signal_name"
                parts = key_str.split("::")
                if len(parts) == 2:
                    symbol, sig_name = parts
                    key_tuple = (symbol, sig_name)

                    # 兼容旧格式（仅时间戳）和新格式（状态对象）
                    if isinstance(value, dict):
                        # 新格式：{"last_score": int, "last_push_ts": float}
                        self._signal_states[key_tuple] = value
                        self._last_signal_time[key_tuple] = value.get("last_push_ts", 0)
                    else:
                        # 旧格式：直接是时间戳
                        self._last_signal_time[key_tuple] = value

            # 清理过期缓存项（超过24小时）
            now = time.time()
            expired_keys = [
                k
                for k, v in self._last_signal_time.items()
                if now - v > 86400  # 24小时
            ]
            for key in expired_keys:
                del self._last_signal_time[key]
                self._signal_states.pop(key, None)

            app_logger.info(
                f"加载信号缓存成功：{len(self._last_signal_time)} 个活跃信号，"
                f"已清理 {len(expired_keys)} 个过期项"
            )
        except Exception as e:
            app_logger.error(f"加载信号缓存失败：{e}，使用空缓存")
            self._last_signal_time = {}
            self._signal_states = {}

    def _save_signal_cache(self):
        """保存信号缓存到磁盘"""
        try:
            # 确保缓存目录存在
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # 转换dict，将tuple key转换为字符串格式
            data = {}
            for (symbol, sig_name), state in self._signal_states.items():
                key_str = f"{symbol}::{sig_name}"
                data[key_str] = state

            with open(SIGNAL_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            app_logger.debug(f"信号缓存已保存：{len(data)} 个信号状态")
        except Exception as e:
            app_logger.error(f"保存信号缓存失败：{e}")

    def start_worker(self):
        if not self._is_running:
            self._is_running = True
            self.start()

    def stop_worker(self):
        self._is_running = False
        # 在停止前保存信号缓存，防止重启后出现重复告警
        self._save_signal_cache()
        self.wait(1000)

    def check_and_trigger_reports(self):
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
                    self._last_report_date = report_key
                    self._last_report_type = report_type
        except Exception as e:
            app_logger.error(f"检查报告生成失败：{e}")

    def generate_daily_summary_report(self, report_type: str = "auto"):
        """生成每日复盘报告

        Args:
            report_type: 报告类型 ("morning", "afternoon", "manual", "auto")
        """
        try:
            if not self.symbols:
                app_logger.warning("无自选股，跳过报告生成")
                return

            app_logger.info(
                f"开始生成 {report_type} 复盘报告，扫描 {len(self.symbols)} 只股票..."
            )

            # 收集所有信号
            all_signals = []
            strong_signals = []

            for symbol in self.symbols:
                try:
                    stock_name = self.fetcher.name_registry.get_name(symbol)
                    code, market, _ = self.engine._parse_symbol(symbol)

                    # 获取最新价格和 K 线
                    p_info = self.engine.get_latest_price_info(symbol)
                    daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)

                    if daily_df.empty or len(daily_df) < 50:
                        continue

                    # 执行技术面分析
                    signals = self.engine.scan_all_timeframes(symbol)

                    # OBV 累积检测
                    obv_signals = self.engine.detect_obv_accumulation(symbol, daily_df)
                    signals.extend(obv_signals)

                    if signals:
                        # 计算强度评分
                        score, audit = (
                            self.engine.calculate_intensity_score_with_symbol(
                                symbol, daily_df, signals
                            )
                        )

                        signal_info = {
                            "symbol": symbol,
                            "name": stock_name,
                            "signals": [s["name"] for s in signals],
                            "score": score,
                            "audit": audit,
                            "price": p_info.get("price", 0),
                            "pct": p_info.get("pct", 0),
                        }

                        all_signals.append(signal_info)

                        # 高分信号单独标记
                        if score >= 3:
                            strong_signals.append(signal_info)

                except Exception as e:
                    app_logger.error(f"扫描 {symbol} 失败：{e}")
                    continue

            # 生成报告内容
            report_title = self._get_report_title(report_type)
            report_content = self._format_report_content(
                report_title, all_signals, strong_signals, report_type
            )

            # 发送报告
            if report_content and self.config:
                NotifierService.dispatch_custom_message(
                    config=self.config,
                    title=report_title,
                    content=report_content,
                    webhook_override=self.wecom_webhook
                    if report_type == "manual"
                    else None,
                )
                app_logger.info(
                    f"复盘报告已发送：{report_title}，共 {len(all_signals)} 个信号"
                )

        except Exception as e:
            app_logger.error(f"生成复盘报告失败：{e}")

    def _get_report_title(self, report_type: str) -> str:
        """获取报告标题"""
        from datetime import datetime

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        titles = {
            "morning": f"📊 早盘复盘 ({date_str})",
            "afternoon": f"📈 午盘复盘 ({date_str})",
            "manual": f"🔍 全量复盘 ({date_str})",
            "auto": f"📉 自动复盘 ({date_str})",
        }

        return titles.get(report_type, titles["auto"])

    def _format_report_content(
        self, title: str, all_signals: list, strong_signals: list, report_type: str
    ) -> str:
        """格式化报告内容（使用 Markdown 格式）"""
        if not all_signals:
            return "今日无显著信号"

        # 按评分排序
        all_signals.sort(key=lambda x: x["score"], reverse=True)
        strong_signals.sort(key=lambda x: x["score"], reverse=True)

        # Markdown 格式报告
        md = [
            f"**{title}**\n\n",
            f"✅ 总信号数：{len(all_signals)} | 🔥 强信号：{len(strong_signals)}\n\n",
        ]

        # 强信号优先展示
        if strong_signals:
            md.append("**🌟 重点关注：**\n")
            for sig in strong_signals[:5]:  # 最多显示 5 个
                fin_label = sig["audit"].get("label", "")
                md.append(
                    f"> **{sig['name']}** ({sig['symbol']}) "
                    f"[{sig['signals'][0]}] "
                    f"评分:{sig['score']:+} "
                    f"{fin_label}"
                )
            md.append("")

        # 全部信号列表
        if all_signals:
            md.append("**📋 全部信号：**\n")
            for sig in all_signals[:20]:  # 最多显示 20 个
                price_info = (
                    f"￥{sig['price']:.2f} ({sig['pct']:+.1f}%)"
                    if sig["price"] > 0
                    else "--"
                )
                md.append(
                    f"• {sig['name']} [{sig['signals'][0]}] "
                    f"+{sig['score']} "
                    f"{price_info}"
                )

        return "\n".join(md)

    def run(self):
        from ...config.manager import load_config
        from ...core.market_manager import MarketManager

        app_logger.info("量化雷达侦测线程已启动...")
        save_cache_counter = 0  # 每10次循环保存一次缓存

        # 首次运行时进行缓存预热
        cache_warming_attempted = False

        while self._is_running:
            try:
                self.config = load_config()
                if not self.config.get("quant_enabled", False):
                    self.msleep(5000)
                    continue

                # 在第一次进入市场开盘时进行缓存预热
                if MarketManager.is_market_open() and not cache_warming_attempted:
                    cache_warming_attempted = True
                    if self.symbols and not self._cache_warmed:
                        app_logger.info("触发缓存预热...")
                        try:
                            self.cache_warmer.warm_cache_for_symbols(
                                self.symbols,
                                categories=[1, 2, 3, 9],  # 15m, 30m, 60m, daily
                                offset=100,
                            )
                            self._cache_warmed = True
                        except Exception as e:
                            app_logger.error(f"缓存预热失败：{e}")

                if MarketManager.is_market_open():
                    current_interval = self.config.get(
                        "quant_scan_interval", self.scan_interval
                    )
                    if (
                        self.symbols
                        and time.time() - self.last_scan_time >= current_interval
                    ):
                        scan_start = time.time()
                        self.perform_scan_parallel()
                        scan_duration = time.time() - scan_start
                        self.perf_monitor.record_scan_time(scan_duration)
                        self.last_scan_time = time.time()

                self.check_and_trigger_reports()

                # 定期保存信号缓存（每10秒保存一次，避免过于频繁的磁盘I/O）
                save_cache_counter += 1
                if save_cache_counter >= 10:
                    self._save_signal_cache()
                    save_cache_counter = 0

            except Exception as e:
                app_logger.error(f"QuantWorker 运行异常：{e}")
            self.msleep(1000)

    def perform_scan(self):
        """对全部自选股执行批量量化扫描（串行兼容入口，委托并行版本执行）"""
        # 直接委托并行版本，线程池大小由配置决定
        # 保留此方法以兼容外部调用
        self.perform_scan_parallel()

    def perform_scan_parallel(self):
        """并行量化扫描（ThreadPoolExecutor 优化版）"""
        self.scan_started.emit()
        app_logger.info(f"开始并行量化扫描，监控标的：{len(self.symbols)} 只")

        if not self.symbols:
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
        max_workers = min(max_workers, len(self.symbols))  # 不超过符号数

        results = []

        app_logger.info(
            f"使用 {max_workers} 个线程扫描（配置: {self.config.get('quant_max_workers', '自动')}, 建议: CPU核心优化）"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有扫描任务
            futures = {
                executor.submit(self._scan_single_symbol, symbol): symbol
                for symbol in self.symbols
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
        """扫描单只股票（供线程池调用）"""
        try:
            stock_name = self.fetcher.name_registry.get_name(symbol)
            code, market, _ = self.engine._parse_symbol(symbol)

            p_info = self.engine.get_latest_price_info(symbol)
            daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)

            signals = self.engine.scan_all_timeframes(symbol)

            obv_signals = self.engine.detect_obv_accumulation(symbol, daily_df)
            for sig in obv_signals:
                signals.append(
                    {
                        "name": f"OBV 低位累积 ({sig['level']})",
                        "tf": "Daily",
                        "time": sig["time"],
                    }
                )

            daily_stats = self.backtester.get_strategy_stats(code, market, category=9)

            is_confluence = False
            rsrs_z, _ = self.engine.calculate_rsrs(daily_df)
            has_macd_div = any(s["name"] == "MACD 底背离" for s in signals)
            if has_macd_div and rsrs_z > 0.7:
                is_confluence = True

            is_priority = False
            wr_label = ""
            if daily_stats and daily_stats.get("total_signals", 0) >= 3:
                if daily_stats["win_rate"] >= 0.8:
                    is_priority = True
                    wr_label = f" [💎 历史胜率 {daily_stats['win_rate'] * 100:.0f}%]"

            score, audit = self.engine.calculate_intensity_score_with_symbol(
                symbol, daily_df, signals
            )

            threshold = 2 if is_priority else 3

            if is_confluence:
                signals.append(
                    {
                        "name": "⚡策略共振 (底背离+RSRS)",
                        "tf": "Daily",
                        "time": time.strftime("%H:%M"),
                    }
                )
                score = max(score, 4)

            if not signals and score >= threshold:
                signals.append(
                    {
                        "name": "多因子综合走强" + wr_label,
                        "tf": "Daily",
                        "time": time.strftime("%H:%M"),
                    }
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

    def _update_signal_state(self, symbol: str, sig_name: str, score: int):
        """更新信号状态记录"""
        state_key = (symbol, sig_name)
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

        # 取最高分作为主评分
        max_score_sig = max(signals_data, key=lambda x: x["score"])

        # 构建精简标题
        is_confluence = any(s.get("is_confluence") for s in signals_data)
        is_priority = any(s.get("is_priority") for s in signals_data)

        if is_confluence:
            title_prefix = "💎【策略共振】"
        elif is_priority:
            title_prefix = "🔥【精细关注】"
        else:
            title_prefix = "🚨"

        # 价格信息
        p_info = max_score_sig.get("p_info", {})

        # 【优化】检查价格有效性
        if p_info and p_info.get("price", 0) > 0:
            pct = p_info.get("pct", 0.0)
            sign = "+" if pct >= 0 else ""
            price_suffix = f" {sign}{pct:.2f}%"
        else:
            price_suffix = " (价格待更新)"
            app_logger.debug(f"[合并推送] {symbol} 价格数据缺失")

        title = f"{title_prefix}{stock_name} ({symbol}){price_suffix}"

        # 构建信号摘要
        score_summary = ", ".join(
            [f"{s['sig_name']}({s['score']:+})" for s in signals_data]
        )

        # 财务审计（取最优）
        best_audit = max(
            signals_data, key=lambda x: x.get("audit", {}).get("score_offset", 0)
        )
        fin_label = best_audit.get("audit", {}).get("label", "[财务稳健]")
        fin_reasons = " / ".join(best_audit.get("audit", {}).get("reasons", []))
        fin_info = f"{fin_label} {fin_reasons}" if fin_reasons else fin_label

        # 历史轨迹
        history_list = self._signals_history.get(symbol, [])
        history_text = ""
        if history_list:
            history_text = "\n今日轨迹：" + " → ".join(
                [f"{h['time']} {h['name']}" for h in history_list[-5:]]  # 最近5条
            )

        # 构建推送内容（Markdown 格式）
        cycle_info = (
            f"信号组合：{score_summary}\n\n"
            f"🚀 **综合强度**：{max_score_sig['score']:+}分\n\n"
            f"🏥 **财务审计**：{fin_info}"
        )

        if history_text:
            cycle_info += f"\n{history_text}"

        return {
            "title": title,
            "signals_text": f"检测到 {len(signals_data)} 个技术信号",
            "cycle_info": cycle_info,
            "p_info": p_info,
            "max_score": max_score_sig["score"],
        }

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
    ) -> dict:
        """
        处理并发送信号（优化版：防抖动 + 信号合并）
        """
        current_time_str = time.strftime("%H:%M")
        triggered = []
        merge_enabled = self.config.get("quant_alert_merge_enabled", True)

        # 【阶段1】收集所有待推送信号
        pending_signals = []

        for sig in signals:
            tf_cn = self.engine.TF_CHINESE_MAP.get(sig.get("tf", "Daily"), "日线")
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

        if not pending_signals:
            return None

        # 【阶段2】根据配置决定是合并推送还是单独推送
        if merge_enabled and len(pending_signals) > 1:
            # 合并推送模式
            merged = self._merge_signals_for_symbol(symbol, stock_name, pending_signals)
            if merged:
                NotifierService.dispatch_alert(
                    config=self.config,
                    symbol=symbol,
                    stock_name=merged["title"].replace(f" ({symbol})", ""),
                    signals=[merged["signals_text"]],
                    cycle_info=merged["cycle_info"],
                    price_info=merged["p_info"],
                )
                app_logger.info(
                    f"发送合并推送：{symbol} ({len(pending_signals)}个信号)"
                )

                # 更新所有信号的状态
                for ps in pending_signals:
                    self._update_signal_state(symbol, ps["sig_name"], ps["score"])
                    triggered.append(ps["sig_name"])
        else:
            # 单独推送模式（保持原有逻辑）
            for ps in pending_signals:
                benchmark_pct, is_valid = self.engine.get_market_relative_strength()
                if not is_valid:
                    app_logger.warning(
                        f"[{symbol}] 大盘数据获取失败，Alpha 计算可能不准确"
                    )
                alpha = ps["p_info"].get("pct", 0.0) - benchmark_pct

                min_backtest_score = 3 if ps["score"] >= 3 else 1
                stats = self.backtester.get_score_stats(
                    symbol,
                    1 if symbol.startswith("sh") else 0,
                    min_score=min_backtest_score,
                )
                stats_text = ""
                if stats and stats.get("total_signals", 0) >= 3:
                    wr = stats["win_rate"] * 100
                    ap = stats["avg_profit"] * 100
                    icon = "✅" if wr >= 60 else ("⚡" if wr >= 45 else "⚠️")
                    stats_text = (
                        f"\n历史复盘：{icon} 同类评分胜率 {wr:.0f}% (均益 {ap:+.1f}%)"
                    )

                fin_label = ps["audit"].get("label", "[财务稳健]")
                fin_reasons = " / ".join(ps["audit"].get("reasons", []))
                fin_info = f"{fin_label} {fin_reasons if fin_reasons else ''}"

                display_name = f"🔥 {stock_name}" if ps["is_priority"] else stock_name
                if ps["is_confluence"]:
                    display_name = f"💎【策略共振】{stock_name}"

                display_sig = " [精细关注]" if ps["is_priority"] else ""
                if ps["is_confluence"]:
                    display_sig = " [超高可靠/重仓机会]"

                cycle_info = f"信号详情：{ps['sig_name']}\n\n"
                cycle_info += (
                    f"🚀 **超值强度**：{ps['score']:+}分 (Alpha: {alpha:+.2f}%)\n\n"
                )
                cycle_info += f"🏥 **财务审计**：{fin_info}\n"
                cycle_info += stats_text

                history_list = self._signals_history.get(symbol, [])
                if history_list:
                    cycle_info += "\n今日轨迹：" + " → ".join(
                        [f"{h['time']} {h['name']}" for h in history_list[-5:]]
                    )

                NotifierService.dispatch_alert(
                    config=self.config,
                    symbol=symbol,
                    stock_name=display_name,
                    signals=[
                        f"{ps['sig_name']}{display_sig} [评分：{ps['score']:+}分]",
                        fin_info,
                    ],
                    cycle_info=cycle_info,
                    price_info=ps["p_info"],
                )
                app_logger.info(
                    f"发送量化异动即时推送：{stock_name} ({ps['sig_name']}) [{ps['reason']}]"
                )

                # 更新状态
                self._update_signal_state(symbol, ps["sig_name"], ps["score"])
                triggered.append(ps["sig_name"])

        # 记录历史轨迹
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

        return {"symbol": symbol, "signals": triggered}
