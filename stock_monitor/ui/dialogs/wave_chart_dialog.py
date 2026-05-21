"""
波浪与斐波那契分析 UI 弹窗
"""

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from PyQt6 import QtCore, QtWidgets

# 设置 matplotlib 全局支持中文字体
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from ...core.engine.wave_analyzer import WaveAnalyzer
from ...utils.logger import app_logger


class WaveChartDialog(QtWidgets.QDialog):
    """
    波浪与斐波那契K线图本地弹窗
    """

    def __init__(self, symbol: str, stock_name: str, engine, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.stock_name = stock_name
        self.engine = engine  # 共享已有的 QuantEngine

        self.setup_ui()
        self.load_and_plot()

    def setup_ui(self):
        self.setWindowTitle(f"波浪理论分析 - {self.stock_name} ({self.symbol})")
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)

        # 整体暗色背景样式
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-family: "Microsoft YaHei";
            }
            QComboBox {
                background-color: #222222;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 8px;
                color: #ffffff;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #222222;
                color: #ffffff;
                selection-background-color: #333333;
            }
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                color: #ffffff;
            }
        """)

        # 主布局
        main_layout = QtWidgets.QVBoxLayout(self)

        # 顶部工具栏布局
        top_bar = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel(
            f"📊 {self.stock_name} ({self.symbol}) 波浪理论及斐波那契分析"
        )
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff7f0e;")
        top_bar.addWidget(title_label)

        top_bar.addStretch()

        # 子浪开关
        self.subwave_cb = QtWidgets.QCheckBox("显示子浪")
        self.subwave_cb.setStyleSheet(
            "color: #ffffff; font-family: 'Microsoft YaHei'; margin-right: 15px;"
        )
        self.subwave_cb.setChecked(False)
        self.subwave_cb.stateChanged.connect(lambda state: self.load_and_plot())
        top_bar.addWidget(self.subwave_cb)

        # 数列（斐波那契）开关
        self.fib_cb = QtWidgets.QCheckBox("显示斐波那契")
        self.fib_cb.setStyleSheet(
            "color: #ffffff; font-family: 'Microsoft YaHei'; margin-right: 15px;"
        )
        self.fib_cb.setChecked(False)
        self.fib_cb.stateChanged.connect(lambda state: self.load_and_plot())
        top_bar.addWidget(self.fib_cb)

        # 周期选择
        period_label = QtWidgets.QLabel("分析周期:")
        top_bar.addWidget(period_label)

        self.period_combo = QtWidgets.QComboBox()
        self.period_combo.addItem("日线", "daily")
        self.period_combo.addItem("60分钟线", "60m")
        self.period_combo.currentIndexChanged.connect(lambda idx: self.load_and_plot())
        top_bar.addWidget(self.period_combo)

        main_layout.addLayout(top_bar)

        # 图形区域
        self.figure, self.ax = plt.subplots(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)

        # Matplotlib 工具栏 (缩放、平移等)
        self.toolbar = NavigationToolbar(self.canvas, self)
        # 简单美化工具栏颜色
        self.toolbar.setStyleSheet(
            "background-color: #1a1a1a; color: #ffffff; border: none; padding: 2px;"
        )
        main_layout.addWidget(self.toolbar)

        # 底部状态栏信息框
        self.info_box = QtWidgets.QGroupBox("结构定位与量化指标")
        info_layout = QtWidgets.QHBoxLayout(self.info_box)

        self.wave_desc_label = QtWidgets.QLabel("正在进行波浪理论定位...")
        self.wave_desc_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.wave_desc_label.setStyleSheet("font-size: 13px; color: #00e5ff;")
        self.wave_desc_label.setWordWrap(True)
        info_layout.addWidget(self.wave_desc_label)

        self.fib_desc_label = QtWidgets.QLabel("斐波那契位加载中...")
        self.fib_desc_label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.fib_desc_label.setStyleSheet("font-size: 12px; color: #a9b7c6;")
        self.fib_desc_label.setWordWrap(True)
        info_layout.addWidget(self.fib_desc_label)

        main_layout.addWidget(self.info_box)

    def load_and_plot(self):
        """
        获取数据、分析、绘制并更新UI
        """
        # 显示加载状态
        self.wave_desc_label.setText("⏳ 正在获取K线数据，进行波浪拟合中...")
        self.fib_desc_label.setText("斐波那契回撤线计算中...")

        timeframe_name = self.period_combo.currentText()
        timeframe_key = self.period_combo.currentData()

        category = 9 if timeframe_key == "daily" else 3  # 9是日线，3是60m

        try:
            # 1. 异步或同步拉取K线
            # 这里在弹窗中同步拉取，因为弹窗是模态的，且是在获取数据后才显示，或者用Qt线程池
            # 为保证体验，我们直接通过已有 client 快速拉取（Mootdx极快）
            app_logger.info(
                f"[波浪图弹窗] 准备拉取K线数据: symbol={self.symbol}, category={category}, offset=100"
            )
            df = self.engine.fetch_bars(self.symbol, category=category, offset=100)
            app_logger.info(
                f"[波浪图弹窗] K线数据拉取完成: symbol={self.symbol}, len={len(df) if df is not None else 'None'}"
            )

            if df is None or df.empty or len(df) < 30:
                app_logger.warning(
                    f"[波浪图弹窗] K线数据不足或为空: symbol={self.symbol}, len={len(df) if df is not None else 'None'}"
                )
                self.wave_desc_label.setText("❌ K线数据不足，无法拟合波浪")
                return

            # 2. 波浪与斐波那契分析
            if self.subwave_cb.isChecked():
                # 勾选显示子浪，使用较小的阈值 0.03
                result = WaveAnalyzer.analyze(df, threshold=0.03)
            else:
                # 只画大浪，尝试较大的大浪阈值（逐步降级以确保能画出来）
                result = None
                for t in [0.08, 0.06, 0.05]:
                    result = WaveAnalyzer.analyze(df, threshold=t)
                    if result:
                        break

            app_logger.info(f"[波浪图弹窗] WaveAnalyzer.analyze(df) 结果: {result}")
            if not result:
                self.wave_desc_label.setText(
                    "❌ 波浪检测未满足基础波动（无法形成波浪形态）"
                )
                return

            # 3. 绘制到嵌入的 canvas 上
            self.plot_to_canvas(result, timeframe_name)

            # 4. 更新文本标签
            cw = result.current_wave
            desc_text = (
                f"🌊 **当前浪位**: {cw.get('desc', '位置未知')}\n"
                f"🏷️ **所处阶段**: 第 {cw.get('wave', '1')} 浪 ({'上升多头' if cw.get('trend') == 'bullish' else '回调调整'})\n"
                f"🎯 **算法置信水平**: {cw.get('confidence', 0.0) * 100:.0f}%"
            )
            self.wave_desc_label.setText(desc_text)

            # 格式化斐波那契位
            if self.fib_cb.isChecked():
                fib_lines = []
                for k, v in result.fib_levels.items():
                    if k not in ("start", "end"):
                        fib_lines.append(f"{k} 位: {v:.2f}")
                fib_text = "📍 **斐波那契关键参考价位**:\n" + "  |  ".join(fib_lines)
            else:
                fib_text = "📍 **斐波那契关键参考价位**: (已隐藏，勾选上方开关可显示)"
            self.fib_desc_label.setText(fib_text)

        except Exception as e:
            app_logger.error(f"本地弹窗波浪画图异常：{e}", exc_info=True)
            self.wave_desc_label.setText(f"❌ 绘图失败: {e}")

    def plot_to_canvas(self, result, timeframe_name: str):
        """
        在 canvas 内部清空并重绘
        """
        self.figure.clear()

        df = result.df.copy()
        swings = result.swings
        fib_levels = result.fib_levels
        _current_wave = result.current_wave  # noqa: F841

        # 仅绘制最近的 80 根 K 线
        plot_len = min(80, len(df))
        start_idx = len(df) - plot_len
        plot_df = df.iloc[start_idx:].copy()
        plot_df.index = pd.to_datetime(plot_df["datetime"])

        # 构造 ZigZag 线
        zigzag_data = pd.Series(index=plot_df.index, dtype=float)
        valid_swings = []
        for s in swings:
            sub_idx = s.index - start_idx
            if 0 <= sub_idx < plot_len:
                dt_label = plot_df.index[sub_idx]
                zigzag_data.loc[dt_label] = s.price
                valid_swings.append((sub_idx, s))

        zigzag_line = zigzag_data.interpolate(method="linear")  # noqa: F841

        # 暗色主题配色（上涨用红色，下跌用绿色）
        mc = mpf.make_marketcolors(
            up="#ff4a4a",
            down="#2ca02c",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        )
        custom_style = mpf.make_mpf_style(
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

        # 传递 ax 参数直接在 figure 指定的 axes 上绘图
        ax = self.figure.add_subplot(111)

        # 绘制K线主图
        mpf.plot(plot_df, type="candle", style=custom_style, ax=ax, volume=False)

        # 绘制波浪折线（按升降趋势区分颜色：上涨用红色，下跌用绿色）
        for i in range(len(valid_swings) - 1):
            x1, swing1 = valid_swings[i]
            x2, swing2 = valid_swings[i + 1]
            color = "#ff4a4a" if swing2.price >= swing1.price else "#2ca02c"
            ax.plot(
                [x1, x2],
                [swing1.price, swing2.price],
                color=color,
                linewidth=2.5,
                alpha=0.9,
                zorder=3,
            )

        # 重新标注
        wave_labels = ["1", "2", "3", "4", "5", "A", "B", "C", "D", "E"]
        extreme_swings = [s for s in valid_swings if s[1].type in ("peak", "trough")]
        y_offset = plot_df["high"].max() * 0.015

        for idx, (sub_idx, swing) in enumerate(extreme_swings):
            label = wave_labels[idx % len(wave_labels)]
            if swing.type == "peak":
                ax.text(
                    sub_idx,
                    swing.price + y_offset,
                    f"({label})\n{swing.price:.2f}",
                    color="#ff4a4a",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                )
            else:
                ax.text(
                    sub_idx,
                    swing.price - y_offset * 1.5,
                    f"({label})\n{swing.price:.2f}",
                    color="#2ca02c",
                    ha="center",
                    va="top",
                    fontsize=9,
                    fontweight="bold",
                )

        # 绘制斐波那契
        if fib_levels and self.fib_cb.isChecked():
            colors = {
                "0.236": "#59a14f",
                "0.382": "#edc948",
                "0.500": "#b07aa1",
                "0.618": "#e15759",
                "0.786": "#9c755f",
                "1.272": "#76b7b2",
                "1.618": "#ff9da7",
            }
            min_x = 0
            max_x = plot_len - 1

            for level_name, price in fib_levels.items():
                if level_name in ("start", "end"):
                    continue
                color = colors.get(level_name, "#888888")
                ax.hlines(
                    y=price,
                    xmin=min_x,
                    xmax=max_x,
                    colors=color,
                    linestyles=":",
                    linewidths=1.0,
                    alpha=0.7,
                )
                ax.text(
                    max_x - 1,
                    price,
                    f" {level_name} ({price:.2f})",
                    color=color,
                    fontsize=8,
                    va="center",
                    ha="left",
                )

        # 加大标题与网格设置
        ax.set_title(
            f"{self.stock_name} ({self.symbol}) {timeframe_name}波浪形态及斐波那契回调阻力位",
            color="#ffffff",
            fontsize=12,
            pad=10,
        )
        ax.grid(True, color="#222222", linestyle="--")

        # 刷新画布
        self.canvas.draw()
