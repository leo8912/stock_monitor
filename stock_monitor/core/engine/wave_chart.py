"""
波浪与斐波那契K线图绘制模块
"""

import os

import matplotlib

matplotlib.use("Agg")  # 强制无GUI模式，防止后台线程绘图崩溃

from typing import Optional

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd

# 设置 matplotlib 全局支持中文字体
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from ...utils.logger import app_logger
from .wave_analyzer import WaveAnalysisResult


class WaveChart:
    """波浪理论与斐波那契图形生成器"""

    @staticmethod
    def generate(
        result: WaveAnalysisResult,
        symbol: str,
        stock_name: str,
        timeframe: str = "daily",
        output_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        绘制K线图，标注波浪走势与斐波那契线，并保存到本地临时目录。
        返回图片保存路径。
        """
        try:
            df = result.df.copy()
            swings = result.swings
            fib_levels = result.fib_levels
            current_wave = result.current_wave

            if df.empty or len(df) < 20:
                return None

            # 创建临时输出目录
            if output_dir is None:
                output_dir = os.path.join(
                    os.environ.get("TEMP", "C:/Windows/Temp"), "stock_monitor_charts"
                )
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{symbol}_wave_{timeframe}.png")

            # 仅绘制最近的80根K线，以防画面过于拥挤
            plot_len = min(80, len(df))
            start_idx = len(df) - plot_len
            plot_df = df.iloc[start_idx:].copy()

            # 必须设置 DatetimeIndex！
            plot_df.index = pd.to_datetime(plot_df["datetime"])

            # 构造 ZigZag 线的数据
            # 在图表时间范围内的端点，连接起来
            zigzag_data = pd.Series(index=plot_df.index, dtype=float)

            # 筛选在绘图范围内的端点
            valid_swings = []
            for s in swings:
                sub_idx = s.index - start_idx
                if 0 <= sub_idx < plot_len:
                    dt_label = plot_df.index[sub_idx]
                    zigzag_data.loc[dt_label] = s.price
                    valid_swings.append((sub_idx, s))

            # 线性插值生成 ZigZag 折线
            _zigzag_line = zigzag_data.interpolate(method="linear")  # noqa: F841

            # 准备绘图样式
            # 采用暗黑色调
            mc = mpf.make_marketcolors(
                up="#ff4a4a",  # 红色上涨
                down="#2ca02c",  # 绿色下跌
                edge="inherit",
                wick="inherit",
                volume="inherit",
            )

            # 使用黑色背景主题
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

            # 绘制K线主图
            fig, axlist = mpf.plot(
                plot_df,
                type="candle",
                style=custom_style,
                volume=False,
                returnfig=True,
                figsize=(10, 6.5),
                title=f"\n{stock_name} ({symbol}) - {timeframe.upper()} WAVE ANALYSIS",
            )

            ax = axlist[0]

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

            # 标注波浪浪号与价格点
            # 自动分配浪号 1,2,3,4,5, A,B,C...
            wave_labels = ["1", "2", "3", "4", "5", "A", "B", "C", "D", "E"]

            # 只对极值点进行标注
            extreme_swings = [
                s for s in valid_swings if s[1].type in ("peak", "trough")
            ]
            for idx, (sub_idx, swing) in enumerate(extreme_swings):
                # 浪号循环使用
                label = wave_labels[idx % len(wave_labels)]

                # 微调文本位置，避免重叠
                y_offset = plot_df["high"].max() * 0.015
                if swing.type == "peak":
                    ax.text(
                        sub_idx,
                        swing.price + y_offset,
                        f"({label})\n{swing.price:.2f}",
                        color="#ff4a4a",
                        ha="center",
                        va="bottom",
                        fontsize=10,
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
                        fontsize=10,
                        fontweight="bold",
                    )

            # 绘制斐波那契回撤水平虚线
            if fib_levels:
                colors = {
                    "0.236": "#59a14f",
                    "0.382": "#edc948",
                    "0.500": "#b07aa1",
                    "0.618": "#e15759",
                    "0.786": "#9c755f",
                    "1.272": "#76b7b2",
                    "1.618": "#ff9da7",
                }

                # 提取有意义的价格区间绘制斐波那契
                min_x = 0
                max_x = plot_len - 1

                for level_name, price in fib_levels.items():
                    if level_name in ("start", "end"):
                        continue

                    color = colors.get(level_name, "#888888")
                    # 绘制水平线
                    ax.hlines(
                        y=price,
                        xmin=min_x,
                        xmax=max_x,
                        colors=color,
                        linestyles=":",
                        linewidths=1.0,
                        alpha=0.7,
                    )
                    # 标注文本
                    ax.text(
                        max_x - 1,
                        price,
                        f" {level_name} ({price:.2f})",
                        color=color,
                        fontsize=8,
                        va="center",
                        ha="left",
                    )

            # 在左上角添加当前浪形位置与置信度文字框
            info_text = (
                f"当前位置: {current_wave.get('desc', '判断中')}\n"
                f"当前浪号: {current_wave.get('wave', '未知')}\n"
                f"趋势类型: {'多头/上升' if current_wave.get('trend') == 'bullish' else '空头/调整'}\n"
                f"置信水平: {current_wave.get('confidence', 0.0) * 100:.0f}%"
            )
            ax.text(
                0.02,
                0.95,
                info_text,
                transform=ax.transAxes,
                fontsize=10,
                color="#ffffff",
                verticalalignment="top",
                bbox={
                    "boxstyle": "round,pad=0.5",
                    "facecolor": "#1e1e1e",
                    "alpha": 0.8,
                    "edgecolor": "#333333",
                },
            )

            # 保存图片并清理绘图资源
            plt.savefig(output_path, dpi=120, bbox_inches="tight", facecolor="#121212")
            plt.close(fig)

            app_logger.info(f"波浪分析图表已成功生成并保存：{output_path}")
            return output_path

        except Exception as e:
            app_logger.error(f"生成波浪图表失败：{e}", exc_info=True)
            try:
                plt.close("all")
            except Exception:  # noqa: E722
                pass
            return None
