"""
量化雷达扫描后台线程
"""

import time

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
        self.config = {}  # 将存储实时配置
        self.scan_interval = scan_interval
        self._is_running = False
        self.last_scan_time = 0
        self.symbols: list[str] = []
        self._alert_cache: set[str] = set()  # 日内信号去重缓存
        self._signal_manager: dict[
            str, float
        ] = {}  # 信号频率控制器 {symbol-key: timestamp}
        self._active_signals: dict[str, dict[str, dict]] = {}
        self._last_signal_time = {}  # {(symbol, signal_name): timestamp}
        self._signals_history = {}  # {symbol: [{"time": "HH:MM", "name": "signal", "score": int}]}
        self._daily_report_times = ["11:35", "15:05"]
        self._last_report_type = ""  # "", "midday", "close"
        self._last_report_date = ""  # "2026-03-30"

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

                # 只有在开盘期间执行量化扫描
                if MarketManager.is_market_open():
                    if (
                        self.symbols
                        and time.time() - self.last_scan_time >= self.scan_interval
                    ):
                        self.perform_scan()
                        self.last_scan_time = time.time()

                # 检查产生总结报告 (即便闭市也要检查，因为 11:35/15:05 在闭市后)
                self.check_and_trigger_reports()

            except Exception as e:
                app_logger.error(f"QuantWorker 运行异常: {e}")
            self.msleep(1000)

    def _build_stats_text(self, symbol: str, market: int, category: int) -> str:
        """根据历史回测结果构造统计文本（含胜率评级 emoji）"""
        stats = self.backtester.get_strategy_stats(symbol, market, category=category)
        if not stats:
            return ""
        n = stats.get("total_signals", 0)
        if n >= 5:
            wr = stats["win_rate"] * 100
            ap = stats["avg_profit"] * 100
            # 胜率评级：≥55% ✅，40-55% ⚡，<40% ⚠️
            icon = "✅" if wr >= 55 else ("⚡" if wr >= 40 else "⚠️")
            return f"，{icon} {n}次 胜率{wr:.0f}% 收益{ap:+.1f}%"
        elif n > 0:
            return f"，{n}次信号（样本少）"
        return ""

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
                market = 1 if symbol.startswith("sh") else 0
                code = symbol[2:] if symbol.startswith(("sh", "sz")) else symbol

                p_info = self.engine.get_latest_price_info(code, market)
                daily_df = self.engine.fetch_bars(code, market, category=9, offset=100)

                # 1. 执行形态扫描
                signals = self.engine.scan_all_timeframes(code, market)

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

                # 3. 计算最终分数
                # 如果当前没有任何特定形态，但分数很高 (Score >= 3)，则作为“高分强度”信号触发
                score, audit = self.engine.calculate_intensity_score_with_symbol(
                    symbol, daily_df, signals
                )
                if not signals and score >= 3:
                    signals.append(
                        {
                            "name": "多因子综合走强",
                            "tf": "Daily",
                            "time": current_time_str,
                        }
                    )

                # 4. 如果检测到量化信号（形态或高分），执行推送
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
                                stock_name=stock_name,
                                signals=[f"{sig_name}  [评分: {score:+}分]", fin_info],
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

    def _get_stock_history_summary(self, symbol: str) -> str:
        """获取个股今日历史异动摘要"""
        history = self._signals_history.get(symbol, [])
        if not history:
            return "今日首个关键信号"

        summary = "今日足迹: " + " → ".join(
            [f"{h['time']} {h['name']}" for h in history]
        )
        return summary

    def check_and_trigger_reports(self):
        """检查并触发早盘/午后总结报告推送"""
        import datetime

        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        hm = now.strftime("%H:%M")

        target_report = ""
        if "11:35" <= hm <= "11:45" and self._last_report_type != "midday":
            target_report = "midday"
        elif "15:05" <= hm <= "15:15" and self._last_report_type != "close":
            target_report = "close"

        if target_report and (
            self._last_report_date != today or self._last_report_type != target_report
        ):
            app_logger.info(f"触发定时报告推送流程: {target_report}")
            self.generate_daily_summary_report(target_report)
            self._last_report_type = target_report
            self._last_report_date = today

    def generate_daily_summary_report(self, report_type: str):
        """生成并推送每日汇总报告"""
        if report_type == "midday":
            title = "☀ 早盘总结"
        elif report_type == "close":
            title = "🌙 全天收盘复盘"
        else:
            title = "📊 手动复盘分析"

        report_items = []
        if not self.symbols:
            return

        total_pct = 0.0
        success_count = 0
        failure_count = 0

        for symbol in self.symbols:
            try:
                market = 1 if symbol.startswith("sh") else 0
                code = symbol[2:]
                stock_name = self.fetcher.name_registry.get_name(symbol)

                # 1. 基础价格表现
                p_info = self.engine.get_latest_price_info(code, market)
                if not p_info:
                    continue

                stock_pct = p_info.get("pct", 0.0)
                total_pct += stock_pct
                if stock_pct > 0:
                    success_count += 1
                elif stock_pct < 0:
                    failure_count += 1

                # 2. 技术体检与评分 (含财务审计)
                daily_df = self.engine.fetch_bars(code, market, category=9, offset=100)
                current_signals = self.engine.scan_all_timeframes(code, market)
                score, audit = self.engine.calculate_intensity_score_with_symbol(
                    symbol, daily_df, current_signals
                )

                # 3. 整理当前信号
                tf_map = self.engine.TF_CHINESE_MAP
                sig_tags = [
                    f"【{tf_map.get(s['tf'], s['tf'])}:{s['name']}】"
                    for s in current_signals
                ]
                sig_str = " ".join(sig_tags) if sig_tags else ""

                # 4. 整理今日流水 (Timeline)
                history = self._signals_history.get(symbol, [])

                # 5. 构造条目
                benchmark_pct = self.engine.get_market_relative_strength()

                # 获取历史胜率参考
                stats = self.backtester.get_score_stats(code, market, min_score=3)
                if stats and stats.get("total_signals", 0) >= 3:
                    pass

                # 美化指标显示
                sig_display = (
                    f"\n> 🏷️ **技术指标**: {sig_str}"
                    if sig_tags
                    else "\n> 🏷️ **技术指标**: 🟡 暂无明显位点"
                )

                # 财务摘要展示
                fin_label = audit.get("label", "[财务稳健]")
                fin_reasons = " / ".join(audit.get("reasons", []))
                fin_display = f"\n> 🏥 **财务审计**: {fin_label} {fin_reasons if fin_reasons else ''}"

                timeline_display = (
                    "\n> 🕒 **今日轨迹**: "
                    + " → ".join([f"{h['time']} {h['name']}" for h in history])
                    if history
                    else ""
                )

                # 强化版标题：**名称** (代码) 价格 (涨跌幅%)
                score_icon = "📈" if score > 0 else ("📉" if score < 0 else "⏺️")
                row = (
                    f"**{stock_name}** ({symbol.upper()})  {p_info['price']:.2f} ({stock_pct:+.2f}%)\n"
                    f"> {score_icon} 量化评分: **{score:+}分**"
                    f"{sig_display}"
                    f"{fin_display}"
                    f"{timeline_display}\n"
                    f"---"
                )
                report_items.append(row)
            except Exception as e:
                app_logger.warning(f"生成报告条目失败 ({symbol}): {e}")
                continue

        if not report_items:
            return "今日自选股无明显异动。"

        # 获取全市场环境信息
        from ...core.market_manager import market_manager

        m_factor, m_desc = self.engine.calculate_market_sentiment_factor()
        m_sentiment = market_manager.get_sentiment()

        header = f"📊 【每日量化监控复盘】 {time.strftime('%Y-%m-%d')}\n"
        header += f"🌏 市场环境: {m_desc} (环境因子: {m_factor:+.1f})\n"
        header += f"📈 涨跌分布: 🆙{m_sentiment.up_count}  ⬇️{m_sentiment.down_count}  ⏺️{m_sentiment.flat_count}\n"
        header += "--------------------\n"

        # 5. 汇总页脚
        avg_pct = total_pct / len(self.symbols) if self.symbols else 0
        benchmark_pct = self.engine.get_market_relative_strength()
        summary_footer = (
            f"监控池表现: 平均 {avg_pct:+.2f}% | 上涨:{success_count} 下跌:{failure_count}\n"
            f"大盘基准({benchmark_pct:+.2f}%)"
        )

        # 6. 推送
        self.notifier.dispatch_report(
            config=self.config,
            title=title,
            content_items=report_items,
            footer=summary_footer,
        )
        app_logger.info("汇总报告推送已发出。")
