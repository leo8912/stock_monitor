"""
量化雷达扫描后台线程（并行优化版）
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6 import QtCore

from ...services.notifier import NotifierService
from ...utils.logger import app_logger
from ..backtest_engine import BacktestEngine
from ..quant_engine import QuantEngine


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
        self._last_signal_time = {}
        self._signals_history = {}
        self._daily_report_times = ["11:35", "15:05"]
        self._last_report_type = ""
        self._last_report_date = ""

        from ...data.stock.stock_db import StockDatabase

        self.db = StockDatabase()

    def set_symbols(self, symbols: list[str]):
        self.symbols = symbols

    def start_worker(self):
        if not self._is_running:
            self._is_running = True
            self.start()

    def stop_worker(self):
        self._is_running = False
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
        """格式化报告内容"""
        if not all_signals:
            return "<div class='gray'>今日无显著信号</div>"

        # 按评分排序
        all_signals.sort(key=lambda x: x["score"], reverse=True)
        strong_signals.sort(key=lambda x: x["score"], reverse=True)

        # HTML 格式报告
        html = [
            '<div style="font-size:14px;line-height:1.6;">',
            f'<div style="color:#1f272e;font-weight:bold;margin-bottom:10px;">{title}</div>',
            '<div style="margin-bottom:15px;">',
            f'<span style="color:#00aa00;">✅ 总信号数：{len(all_signals)}</span> | ',
            f'<span style="color:#ff6b6b;">🔥 强信号：{len(strong_signals)}</span>',
            "</div>",
        ]

        # 强信号优先展示
        if strong_signals:
            html.append(
                '<div style="margin-bottom:15px;"><strong>🌟 重点关注：</strong></div>'
            )
            for sig in strong_signals[:5]:  # 最多显示 5 个
                fin_label = sig["audit"].get("label", "")
                html.append(
                    f'<div style="padding:5px;margin:5px 0;background:#f8f9fa;border-left:3px solid #ff6b6b;">'
                    f'<strong>{sig["name"]}</strong> ({sig["symbol"]}) '
                    f'<span style="color:#ff6b6b;">[{sig["signals"][0]}]</span> '
                    f'<span style="color:#00aa00;">评分:{sig["score"]:+}</span> '
                    f'{fin_label}'
                    f'</div>'
                )

        # 全部信号列表
        if all_signals:
            html.append(
                '<div style="margin-top:15px;"><strong>📋 全部信号：</strong></div>'
            )
            for sig in all_signals[:20]:  # 最多显示 20 个
                price_info = (
                    f'￥{sig["price"]:.2f} ({sig["pct"]:+.1f}%)'
                    if sig["price"] > 0
                    else "--"
                )
                html.append(
                    f'<div style="padding:3px;margin:3px 0;color:#555;">'
                    f'• {sig["name"]} [{sig["signals"][0]}] '
                    f'<span style="color:#00aa00;">+{sig["score"]}</span> '
                    f'{price_info}'
                    f'</div>'
                )

        html.append("</div>")

        return "\n".join(html)

    def run(self):
        from ...config.manager import load_config
        from ...core.market_manager import MarketManager

        app_logger.info("量化雷达侦测线程已启动...")
        while self._is_running:
            try:
                self.config = load_config()
                if not self.config.get("quant_enabled", False):
                    self.msleep(5000)
                    continue

                if MarketManager.is_market_open():
                    current_interval = self.config.get(
                        "quant_scan_interval", self.scan_interval
                    )
                    if (
                        self.symbols
                        and time.time() - self.last_scan_time >= current_interval
                    ):
                        self.perform_scan_parallel()
                        self.last_scan_time = time.time()

                self.check_and_trigger_reports()

            except Exception as e:
                app_logger.error(f"QuantWorker 运行异常：{e}")
            self.msleep(1000)

    def perform_scan(self):
        """对全部自选股执行批量量化扫描"""
        self.scan_started.emit()
        app_logger.info(f"开始量化扫描，监控标的: {len(self.symbols)} 只")
        now = time.time()
        current_time_str = time.strftime("%H:%M")

        for symbol in self.symbols:
            if not self._is_running:
                break
            try:
                stock_name = self.fetcher.name_registry.get_name(symbol)

                # 解析代码和市场，用于兼容低层 API (如回测)
                code, market, _ = self.engine._parse_symbol(symbol)

                # 获取最新价格和K线
                p_info = self.engine.get_latest_price_info(symbol)
                daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)

                # 1. 执行形态扫描
                signals = self.engine.scan_all_timeframes(symbol)

                # 2. 策略检测 2: OBV 累积 (成交量异常)
                obv_signals = self.engine.detect_obv_accumulation(symbol, daily_df)
                for sig in obv_signals:
                    signals.append(
                        {
                            "name": f"OBV低位累积({sig['level']})",
                            "tf": "Daily",
                            "time": sig["time"],
                        }
                    )

                # 3. 核心可靠性检查 (新增强化逻辑)
                # 检查日线级别 MACD 底背离的历史可靠性
                daily_stats = self.backtester.get_strategy_stats(
                    code, market, category=9
                )

                # 新增：共振模型检查 (Confluence)
                is_confluence = False
                rsrs_z, _ = self.engine.calculate_rsrs(daily_df)
                has_macd_div = any(s["name"] == "MACD底背离" for s in signals)
                if has_macd_div and rsrs_z > 0.7:
                    is_confluence = True

                is_priority = False
                wr_label = ""
                if daily_stats and daily_stats.get("total_signals", 0) >= 3:
                    if daily_stats["win_rate"] >= 0.8:
                        is_priority = True
                        wr_label = (
                            f" [💎 历史胜率 {daily_stats['win_rate'] * 100:.0f}%]"
                        )

                # 4. 计算最终分数并判定触发阈值
                score, audit = self.engine.calculate_intensity_score_with_symbol(
                    symbol, daily_df, signals
                )

                # 弹性阈值：高可靠品种只需 2 分，普通品种 3 分
                threshold = 2 if is_priority else 3

                # 共振信号强制触发
                if is_confluence:
                    signals.append(
                        {
                            "name": "⚡策略共振(底背离+RSRS)",
                            "tf": "Daily",
                            "time": current_time_str,
                        }
                    )
                    score = max(score, 4)  # 强制高分

                if not signals and score >= threshold:
                    signals.append(
                        {
                            "name": "多因子综合走强" + wr_label,
                            "tf": "Daily",
                            "time": current_time_str,
                        }
                    )

                # 5. 如果检测到量化信号，执行推送
                if signals:
                    for sig in signals:
                        tf_cn = self.engine.TF_CHINESE_MAP.get(
                            sig.get("tf", "Daily"), sig.get("tf", "Daily")
                        )
                        sig_name = f"{tf_cn}:{sig['name']}"
                        last_t = self._last_signal_time.get((symbol, sig_name), 0)

                        # 核心逻辑：如果是新信号或是 30 分钟冷却期后，执行推送
                        if now - last_t > 1800:
                            # 记录到当日历史流水
                            if symbol not in self._signals_history:
                                self._signals_history[symbol] = []

                            self._signals_history[symbol].append(
                                {
                                    "time": current_time_str,
                                    "name": sig_name,
                                    "score": score,
                                }
                            )

                            # 记录最后触发时间，用于冷却期控制
                            self._last_signal_time[(symbol, sig_name)] = now

                            # 构造增强版推送信息
                            # 获取超额收益 (Alpha)
                            benchmark_pct = self.engine.get_market_relative_strength()
                            alpha = p_info.get("pct", 0.0) - benchmark_pct

                            # 获取历史评分胜率 (对应该评分区间的表现)
                            # 如果 score=4 则查 >=3 的表现
                            min_backtest_score = 3 if score >= 3 else 1
                            stats = self.backtester.get_score_stats(
                                symbol, market, min_score=min_backtest_score
                            )
                            stats_text = ""
                            if stats and stats.get("total_signals", 0) >= 3:
                                wr = stats["win_rate"] * 100
                                ap = stats["avg_profit"] * 100
                                icon = "✅" if wr >= 60 else ("⚡" if wr >= 45 else "⚠️")
                                stats_text = f'\n<div class="gray">历史复盘: {icon} 同类评分胜率 {wr:.0f}% (均益 {ap:+.1f}%)</div>'

                            # 获取更直观的标签
                            fin_label = audit.get("label", "[财务稳健]")
                            fin_reasons = " / ".join(audit.get("reasons", []))
                            fin_info = (
                                f"{fin_label} {fin_reasons if fin_reasons else ''}"
                            )

                            # 高可靠品种标题增强
                            display_name = (
                                f"🔥 {stock_name}" if is_priority else stock_name
                            )
                            if is_confluence:
                                display_name = f"💎【策略共振】{stock_name}"

                            display_sig = " [精细关注]" if is_priority else ""
                            if is_confluence:
                                display_sig = " [超高可靠/重仓机会]"

                            # 组装展示内容
                            cycle_info = (
                                f'<div class="gray">信号详情: {sig_name}</div>\n'
                            )
                            cycle_info += f'<div class="highlight">🚀 超值强度: {score:+}分 (Alpha: {alpha:+.2f}%)</div>\n'
                            cycle_info += (
                                f'<div class="orange">🏥 财务审计: {fin_info}</div>\n'
                            )
                            cycle_info += stats_text

                            history_list = self._signals_history.get(symbol, [])
                            if history_list:
                                cycle_info += "\n今日轨迹: " + " → ".join(
                                    [f"{h['time']} {h['name']}" for h in history_list]
                                )

                            from stock_monitor.services.notifier import NotifierService

                            NotifierService.dispatch_alert(
                                config=self.config,
                                symbol=symbol,
                                stock_name=display_name,
                                signals=[
                                    f"{sig_name}{display_sig} [评分: {score:+}分]",
                                    fin_info,
                                ],
                                cycle_info=cycle_info,
                                price_info=p_info,
                            )
                            app_logger.info(
                                f"发送量化异动即时推送: {stock_name} ({sig_name})"
                            )

            except Exception as e:
                app_logger.error(f"标的 {symbol} 扫描异常: {e}")
            time.sleep(0.3)

        self.scan_finished.emit()
        app_logger.info("本轮量化扫描完毕")

    def perform_scan_parallel(self):
        """并行量化扫描（ThreadPoolExecutor 优化版）"""
        self.scan_started.emit()
        app_logger.info(f"开始并行量化扫描，监控标的：{len(self.symbols)} 只")

        if not self.symbols:
            self.scan_finished.emit()
            return

        # 使用线程池并行处理，每只股票独立线程
        max_workers = min(10, len(self.symbols))  # 最多 10 个并发线程
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有扫描任务
            futures = {
                executor.submit(self._scan_single_symbol, symbol): symbol
                for symbol in self.symbols
            }

            # 收集结果
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
        """处理并发送信号"""
        now = time.time()
        current_time_str = time.strftime("%H:%M")
        triggered = []

        for sig in signals:
            tf_cn = self.engine.TF_CHINESE_MAP.get(sig.get("tf", "Daily"), "日线")
            sig_name = f"{tf_cn}:{sig['name']}"
            last_t = self._last_signal_time.get((symbol, sig_name), 0)

            if now - last_t > 1800:  # 30 分钟冷却
                if symbol not in self._signals_history:
                    self._signals_history[symbol] = []

                self._signals_history[symbol].append(
                    {
                        "time": current_time_str,
                        "name": sig_name,
                        "score": score,
                    }
                )

                self._last_signal_time[(symbol, sig_name)] = now

                benchmark_pct = self.engine.get_market_relative_strength()
                alpha = p_info.get("pct", 0.0) - benchmark_pct

                min_backtest_score = 3 if score >= 3 else 1
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
                    stats_text = f'\n<div class="gray">历史复盘：{icon} 同类评分胜率 {wr:.0f}% (均益 {ap:+.1f}%)</div>'

                fin_label = audit.get("label", "[财务稳健]")
                fin_reasons = " / ".join(audit.get("reasons", []))
                fin_info = f"{fin_label} {fin_reasons if fin_reasons else ''}"

                display_name = f"🔥 {stock_name}" if is_priority else stock_name
                if is_confluence:
                    display_name = f"💎【策略共振】{stock_name}"

                display_sig = " [精细关注]" if is_priority else ""
                if is_confluence:
                    display_sig = " [超高可靠/重仓机会]"

                cycle_info = f'<div class="gray">信号详情：{sig_name}</div>\n'
                cycle_info += f'<div class="highlight">🚀 超值强度：{score:+}分 (Alpha: {alpha:+.2f}%)</div>\n'
                cycle_info += f'<div class="orange">🏥 财务审计：{fin_info}</div>\n'
                cycle_info += stats_text

                history_list = self._signals_history.get(symbol, [])
                if history_list:
                    cycle_info += "\n今日轨迹：" + " → ".join(
                        [f"{h['time']} {h['name']}" for h in history_list]
                    )

                NotifierService.dispatch_alert(
                    config=self.config,
                    symbol=symbol,
                    stock_name=display_name,
                    signals=[
                        f"{sig_name}{display_sig} [评分：{score:+}分]",
                        fin_info,
                    ],
                    cycle_info=cycle_info,
                    price_info=p_info,
                )
                app_logger.info(f"发送量化异动即时推送：{stock_name} ({sig_name})")
                triggered.append(sig_name)

        return {"symbol": symbol, "signals": triggered}
