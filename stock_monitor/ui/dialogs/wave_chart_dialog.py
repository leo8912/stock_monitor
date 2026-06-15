"""
波浪与斐波那契分析 UI 弹窗
"""

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PyQt6 import QtWidgets

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from ...core.engine.wave_analyzer import WaveAnalyzer
from ...utils.logger import app_logger

CARD_BG = "#1e1e1e"
CARD_BORDER = "#333333"
CARD_RADIUS = "6px"
TEXT_COLOR = "#cccccc"
TEXT_DIM = "#888888"
RED = "#ff4a4a"
GREEN = "#2ca02c"
YELLOW = "#ffcc00"
WHITE = "#ffffff"


class WaveChartDialog(QtWidgets.QDialog):
    """波浪与斐波那契K线图本地弹窗"""

    def __init__(self, symbol: str, stock_name: str, engine, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.stock_name = stock_name
        self.engine = engine
        self._card_labels: dict[str, QtWidgets.QLabel] = {}
        self.setup_ui()
        self.load_and_plot()

    def setup_ui(self):
        self.setWindowTitle(f"波浪分析 - {self.stock_name} ({self.symbol})")
        self.resize(1100, 750)
        self.setMinimumSize(900, 650)

        self.setStyleSheet(f"""
            QDialog {{ background-color: #121212; color: {WHITE}; }}
            QLabel {{ color: {TEXT_COLOR}; font-family: "Microsoft YaHei"; }}
            QComboBox {{
                background-color: #222222; border: 1px solid #444444;
                border-radius: 4px; padding: 4px 8px; color: {WHITE}; min-width: 100px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: #222222; color: {WHITE};
                selection-background-color: #333333;
            }}
            QCheckBox {{
                color: {WHITE}; font-family: "Microsoft YaHei"; margin-right: 15px;
            }}
        """)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(4)

        # 顶部工具栏
        top_bar = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(f"{self.stock_name} ({self.symbol}) 波浪分析")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #ff7f0e;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.subwave_cb = QtWidgets.QCheckBox("显示子浪")
        self.subwave_cb.setChecked(False)
        self.subwave_cb.stateChanged.connect(lambda _: self.load_and_plot())
        top_bar.addWidget(self.subwave_cb)

        self.fib_cb = QtWidgets.QCheckBox("显示斐波那契")
        self.fib_cb.setChecked(False)
        self.fib_cb.stateChanged.connect(lambda _: self.load_and_plot())
        top_bar.addWidget(self.fib_cb)

        period_label = QtWidgets.QLabel("周期:")
        top_bar.addWidget(period_label)
        self.period_combo = QtWidgets.QComboBox()
        self.period_combo.addItem("日线", "daily")
        self.period_combo.addItem("60分钟线", "60m")
        self.period_combo.currentIndexChanged.connect(lambda _: self.load_and_plot())
        top_bar.addWidget(self.period_combo)
        main_layout.addLayout(top_bar)

        # 图形区域
        self.figure = plt.figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas, stretch=1)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet(
            "background-color: #1a1a1a; color: #ffffff; border: none; padding: 2px;"
        )
        main_layout.addWidget(self.toolbar)

        # 底部三列卡片
        self._setup_info_cards(main_layout)

    def _setup_info_cards(self, parent_layout):
        info_box = QtWidgets.QFrame()
        info_box.setStyleSheet(f"""
            QFrame {{
                background-color: #1a1a1a;
                border: 1px solid {CARD_BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
        """)
        cards_layout = QtWidgets.QVBoxLayout(info_box)
        cards_layout.setContentsMargins(8, 8, 8, 8)
        cards_layout.setSpacing(6)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)

        # 卡片1: 当前浪位
        card1 = self._make_card()
        self._card_labels["wave_title"] = self._card_header(card1, "当前浪位")
        self._card_labels["wave_main"] = self._card_label(
            card1, "", f"font-size: 18px; font-weight: bold; color: {WHITE};"
        )
        self._card_labels["wave_trend"] = self._card_label(
            card1, "", f"font-size: 12px; color: {TEXT_COLOR};"
        )
        self._card_labels["wave_desc"] = self._card_label(
            card1, "", f"font-size: 11px; color: {TEXT_DIM};"
        )
        self._card_labels["wave_hint"] = self._card_label(
            card1, "", f"font-size: 11px; color: {TEXT_DIM};"
        )
        row.addWidget(card1, stretch=1)

        # 卡片2: 近期走势
        card2 = self._make_card()
        self._card_labels["trend_title"] = self._card_header(card2, "近期走势")
        self._trend_container = QtWidgets.QVBoxLayout()
        self._trend_container.setSpacing(2)
        card2.layout().addLayout(self._trend_container)
        row.addWidget(card2, stretch=1)

        # 卡片3: 空间预估
        card3 = self._make_card()
        self._card_labels["space_title"] = self._card_header(card3, "空间预估")
        self._card_labels["space_target"] = self._card_label(
            card3, "", f"font-size: 16px; font-weight: bold; color: {YELLOW};"
        )
        self._card_labels["space_remain"] = self._card_label(
            card3, "", f"font-size: 13px; color: {TEXT_COLOR};"
        )
        self._card_labels["space_days"] = self._card_label(
            card3, "", f"font-size: 11px; color: {TEXT_DIM};"
        )
        row.addWidget(card3, stretch=1)

        cards_layout.addLayout(row)

        # Fibonacci 行
        self._card_labels["fib"] = QtWidgets.QLabel("")
        self._card_labels["fib"].setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; padding: 2px 4px;"
        )
        self._card_labels["fib"].setWordWrap(True)
        cards_layout.addWidget(self._card_labels["fib"])

        parent_layout.addWidget(info_box)

    @staticmethod
    def _make_card():
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: {CARD_RADIUS};
                padding: 8px;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)
        return card

    @staticmethod
    def _card_header(parent, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: bold; border: none;"
        )
        parent.layout().addWidget(lbl)
        return lbl

    @staticmethod
    def _card_label(parent, text, style):
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet(f"color: {TEXT_COLOR}; {style} border: none;")
        lbl.setWordWrap(True)
        parent.layout().addWidget(lbl)
        return lbl

    def closeEvent(self, event):
        try:
            plt.close(self.figure)
            self.figure.clear()
        except Exception:
            pass
        super().closeEvent(event)

    def load_and_plot(self):
        self._card_labels["wave_main"].setText("加载中...")
        self._card_labels["wave_trend"].setText("")
        self._card_labels["wave_desc"].setText("")
        self._card_labels["wave_hint"].setText("")

        timeframe_name = self.period_combo.currentText()
        timeframe_key = self.period_combo.currentData()
        category = 9 if timeframe_key == "daily" else 3

        try:
            app_logger.info(
                f"[波浪图弹窗] 拉取K线: symbol={self.symbol}, category={category}, offset=350"
            )
            df = self.engine.fetch_bars(self.symbol, category=category, offset=350)
            if df is None or df.empty or len(df) < 30:
                self._card_labels["wave_main"].setText("数据不足")
                return

            result = None
            if self.subwave_cb.isChecked():
                result = WaveAnalyzer.analyze(df, threshold=0.03)
            else:
                for t in [0.08, 0.06, 0.05]:
                    result = WaveAnalyzer.analyze(df, threshold=t)
                    if result:
                        break

            if not result:
                self._card_labels["wave_main"].setText("无法识别波浪")
                return

            self.plot_to_canvas(result, timeframe_name)
            self._update_cards(result)

        except Exception as e:
            app_logger.error(f"[波浪图弹窗] 异常: {e}", exc_info=True)
            self._card_labels["wave_main"].setText(f"失败: {e}")

    def _update_cards(self, result):
        cw = result.current_wave
        wave = cw.get("wave", "?")
        trend = cw.get("trend", "")
        conf = cw.get("confidence", 0) * 100
        trend_text = "看涨" if trend == "bullish" else "看跌"
        trend_color = RED if trend == "bullish" else GREEN

        # 卡片1: 当前浪位
        self._card_labels["wave_main"].setText(f"第{wave}浪")
        self._card_labels["wave_main"].setStyleSheet(
            f"color: {trend_color}; font-size: 18px; font-weight: bold; border: none;"
        )
        self._card_labels["wave_trend"].setText(f"{trend_text} | 置信度 {conf:.0f}%")
        self._card_labels["wave_desc"].setText(
            WaveChartDialog._explain_wave(wave, trend)
        )
        self._card_labels["wave_hint"].setText(WaveChartDialog._wave_hint(wave, trend))

        # 卡片2: 近期走势（清空重建）
        while self._trend_container.count():
            item = self._trend_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for wd in result.all_waves:
            is_up = wd["direction"] == "up"
            color = RED if is_up else GREEN
            arrow = "↑" if is_up else "↓"
            sign = "+" if wd["pct_change"] >= 0 else ""
            marker = " ←当前位置" if wd["is_current"] else ""
            dur = f"{wd['duration_days']}天" if wd["duration_days"] > 0 else "?"
            text = (
                f"{arrow} {wd['label']}: {wd['from_date'][5:]}→{wd['to_date'][5:]} "
                f"({dur}) {sign}{wd['pct_change']:.1f}%{marker}"
            )
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(
                f"color: {WHITE if wd['is_current'] else color}; "
                f"font-size: 11px; font-weight: {'bold' if wd['is_current'] else 'normal'}; "
                f"border: none;"
            )
            self._trend_container.addWidget(lbl)

        # 卡片3: 空间预估
        rs = result.remaining_space
        if rs:
            sign = "+" if rs["remaining_pct"] >= 0 else ""
            self._card_labels["space_target"].setText(f"目标: {rs['target_price']:.2f}")
            self._card_labels["space_remain"].setText(
                f"剩余: {sign}{rs['remaining_pct']:.1f}% ({rs['basis']})"
            )
            self._card_labels["space_days"].setText(
                f"约{rs['remaining_days_est']}个交易日"
            )
        else:
            self._card_labels["space_target"].setText("暂无数据")
            self._card_labels["space_remain"].setText("")
            self._card_labels["space_days"].setText("")

        # Fibonacci 行
        fib_levels = result.fib_levels
        if fib_levels:
            sorted_fib = sorted(
                [(k, v) for k, v in fib_levels.items() if k not in ("start", "end")],
                key=lambda x: x[1],
            )
            parts = [f"{k}={v:.2f}" for k, v in sorted_fib]
            self._card_labels["fib"].setText("Fibonacci: " + " | ".join(parts))
        else:
            self._card_labels["fib"].setText("")

    def plot_to_canvas(self, result, timeframe_name: str):
        self.figure.clear()

        df = result.df.copy()
        swings = result.swings
        fib_levels = result.fib_levels
        current_wave = result.current_wave

        # K线图占88%，右侧价格栏占12%
        ax = self.figure.add_axes([0.06, 0.08, 0.80, 0.84])
        ax2 = self.figure.add_axes([0.88, 0.08, 0.11, 0.84])

        # 最近80根K线
        plot_len = min(80, len(df))
        start_idx = len(df) - plot_len
        plot_df = df.iloc[start_idx:].copy()
        plot_df.index = pd.to_datetime(plot_df["datetime"])

        # ZigZag线数据
        zigzag_data = pd.Series(index=plot_df.index, dtype=float)
        valid_swings = []
        for s in swings:
            sub_idx = s.index - start_idx
            if 0 <= sub_idx < plot_len:
                dt_label = plot_df.index[sub_idx]
                zigzag_data.loc[dt_label] = s.price
                valid_swings.append((sub_idx, s))

        # 暗色主题
        mc = mpf.make_marketcolors(
            up=RED, down=GREEN, edge="inherit", wick="inherit", volume="inherit"
        )
        style = mpf.make_mpf_style(
            base_mpf_style="charles",
            marketcolors=mc,
            facecolor="#121212",
            gridcolor="#222222",
            figcolor="#121212",
            gridstyle="--",
            rc={
                "text.color": "#cccccc",
                "axes.labelcolor": "#cccccc",
                "xtick.color": "#888888",
                "ytick.color": "#888888",
                "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
                "axes.unicode_minus": False,
            },
        )

        mpf.plot(plot_df, type="candle", style=style, ax=ax, volume=False)

        # ZigZag折线
        for i in range(len(valid_swings) - 1):
            x1, s1 = valid_swings[i]
            x2, s2 = valid_swings[i + 1]
            color = RED if s2.price >= s1.price else GREEN
            ax.plot(
                [x1, x2],
                [s1.price, s2.price],
                color=color,
                linewidth=2.0,
                alpha=0.9,
                zorder=3,
            )

        # 精简浪号标注（最近4个极值点，圈号）
        wave_labels_circle = ["①", "②", "③", "④", "⑤", "Ⓐ", "Ⓑ", "Ⓒ"]
        extreme_swings = [s for s in valid_swings if s[1].type in ("peak", "trough")]
        recent = extreme_swings[-4:] if len(extreme_swings) > 4 else extreme_swings
        y_off = plot_df["high"].max() * 0.015

        for idx, (sub_idx, swing) in enumerate(recent):
            label = wave_labels_circle[idx % len(wave_labels_circle)]
            if swing.type == "peak":
                ax.text(
                    sub_idx,
                    swing.price + y_off,
                    f"{label}\n{swing.price:.2f}",
                    color=RED,
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )
            else:
                ax.text(
                    sub_idx,
                    swing.price - y_off * 1.5,
                    f"{label}\n{swing.price:.2f}",
                    color=GREEN,
                    ha="center",
                    va="top",
                    fontsize=9,
                    fontweight="bold",
                )

        # Fibonacci虚线（勾选时）
        if fib_levels and self.fib_cb.isChecked():
            fib_colors = {
                "0.236": "#59a14f",
                "0.382": "#edc948",
                "0.500": "#b07aa1",
                "0.618": "#e15759",
                "0.786": "#9c755f",
                "1.272": "#76b7b2",
                "1.618": "#ff9da7",
            }
            for name, price in fib_levels.items():
                if name in ("start", "end"):
                    continue
                c = fib_colors.get(name, "#888888")
                ax.hlines(
                    y=price,
                    xmin=0,
                    xmax=plot_len - 1,
                    colors=c,
                    linestyles=":",
                    linewidths=0.8,
                    alpha=0.6,
                )

        ax.set_title(
            f"{self.stock_name} ({self.symbol}) {timeframe_name}",
            color="#ffffff",
            fontsize=11,
            pad=8,
        )
        ax.grid(True, color="#222222", linestyle="--")

        # 右侧价格栏
        curr_price = float(df.iloc[-1]["close"])
        self._draw_price_bar(
            ax2, ax, curr_price, fib_levels, current_wave, result.remaining_space
        )

        self.canvas.draw()

    def _draw_price_bar(
        self, ax2, ax_main, curr_price, fib_levels, current_wave, remaining_space
    ):
        ax2.set_xlim(0, 1)
        ax2.set_ylim(ax_main.get_ylim())
        ax2.axis("off")
        ax2.set_facecolor("#121212")

        # 收集价位，按趋势分组
        supports = []
        resistances = []

        for name, price in fib_levels.items():
            if name in ("start", "end"):
                continue
            if price > curr_price:
                resistances.append((name, price))
            else:
                supports.append((name, price))

        # 目标位
        if remaining_space:
            target = remaining_space["target_price"]
            label = f"目标({remaining_space['basis']})"
            if target > curr_price:
                resistances.insert(0, (label, target))
            else:
                supports.insert(0, (label, target))

        resistances.sort(key=lambda x: x[1])
        supports.sort(key=lambda x: -x[1])

        def _draw_tag(ax, x, y, text, color, bg, fontsize=9, va="center"):
            ax.text(
                x,
                y,
                f" {text} ",
                transform=ax.get_yaxis_transform(),
                color=color,
                fontsize=fontsize,
                ha="left",
                va=va,
                fontweight="bold",
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": bg,
                    "alpha": 0.85,
                    "edgecolor": "none",
                },
            )

        # 阻力位（当前价上方）
        for name, price in resistances:
            ax2.axhline(y=price, color=RED, linewidth=0.6, linestyle="--", alpha=0.5)
            is_target = "目标" in name
            _draw_tag(
                ax2,
                0.05,
                price,
                f"{name} {price:.2f}",
                RED if not is_target else YELLOW,
                "#331111" if not is_target else "#332200",
                fontsize=8 if not is_target else 9,
                va="bottom",
            )

        # 当前价（最醒目）
        ax2.axhline(y=curr_price, color=WHITE, linewidth=1.5, linestyle="-", alpha=0.8)
        ax2.text(
            0.05,
            curr_price,
            f" {curr_price:.2f} ",
            transform=ax2.get_yaxis_transform(),
            color=WHITE,
            fontsize=11,
            fontweight="bold",
            ha="left",
            va="center",
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "#333333",
                "edgecolor": "#555555",
                "alpha": 0.9,
            },
        )

        # 支撑位（当前价下方）
        for name, price in supports:
            ax2.axhline(y=price, color=GREEN, linewidth=0.6, linestyle="--", alpha=0.5)
            is_target = "目标" in name
            _draw_tag(
                ax2,
                0.05,
                price,
                f"{name} {price:.2f}",
                GREEN if not is_target else YELLOW,
                "#113311" if not is_target else "#332200",
                fontsize=8 if not is_target else 9,
                va="top",
            )

    @staticmethod
    def _explain_wave(wave, trend):
        explanations = {
            ("1", "bullish"): "筑底完成，刚刚启动上涨",
            ("2", "bullish"): "上涨后回踩确认，正常调整",
            ("3", "bullish"): "主升浪，涨幅最大、速度最快",
            ("4", "bullish"): "上涨途中休整，蓄力再冲高",
            ("5", "bullish"): "上涨末期，动能衰减，追高风险大",
            ("A", "bearish"): "上涨结束，开始下跌调整",
            ("B", "bearish"): "下跌途中的反弹，空间有限",
            ("C", "bearish"): "加速下跌阶段，杀伤力最大",
        }
        return explanations.get((wave, trend), "震荡筑底阶段，方向待确认")

    @staticmethod
    def _wave_hint(wave, trend):
        hints = {
            ("1", "bullish"): "建议: 底部确认后可小仓试探",
            ("2", "bullish"): "建议: 回调企稳是加仓机会",
            ("3", "bullish"): "建议: 持股待涨，不轻易下车",
            ("4", "bullish"): "建议: 耐心持有，等调整结束再加仓",
            ("5", "bullish"): "建议: 逢高减仓，锁定利润",
            ("A", "bearish"): "建议: 止损离场，不要死扛",
            ("B", "bearish"): "建议: 反弹是逃命机会，别追",
            ("C", "bearish"): "建议: 等企稳再考虑入场",
        }
        return hints.get((wave, trend), "建议: 观望为主，等方向明确")
