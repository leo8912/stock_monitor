"""
波浪理论与斐波那契数列分析引擎
"""

from typing import Any, Optional

import pandas as pd

from ...utils.logger import app_logger
from .quant_engine_constants import WAVE_MIN_K_COUNT, WAVE_ZIGZAG_THRESHOLD


class SwingPoint:
    def __init__(self, index: int, type: str, price: float, date_str: str):
        self.index = index
        self.type = type  # 'peak' (高点) or 'trough' (低点) or 'current' (最新点)
        self.price = price
        self.date_str = date_str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "type": self.type,
            "price": self.price,
            "date": self.date_str,
        }


class WaveAnalysisResult:
    def __init__(
        self,
        df: pd.DataFrame,
        swings: list[SwingPoint],
        current_wave: dict[str, Any],
        fib_levels: dict[str, float],
        all_waves: list[dict[str, Any]],
    ):
        self.df = df
        self.swings = swings
        self.current_wave = current_wave
        self.fib_levels = fib_levels
        self.all_waves = all_waves


class WaveAnalyzer:
    """波浪理论与斐波那契计算分析器"""

    @staticmethod
    def detect_zigzag(
        df: pd.DataFrame, threshold: float = WAVE_ZIGZAG_THRESHOLD
    ) -> list[SwingPoint]:
        """
        利用 ZigZag 算法检测K线的高低摆动点
        """
        if df.empty or len(df) < 5:
            return []

        highs = df["high"].values
        lows = df["low"].values
        dates = (
            df["datetime"].astype(str).values
            if "datetime" in df.columns
            else df.index.astype(str).values
        )

        swings: list[SwingPoint] = []

        # 初始模式搜索：寻找第一个超过阈值的波动
        mode = None  # 'peak' (找低点/转折为trough) or 'trough' (找高点/转折为peak)
        last_extreme_idx = 0

        for i in range(1, len(df)):
            if mode is None:
                h_diff = (highs[i] - lows[0]) / lows[0] if lows[0] != 0 else 0
                l_diff = (highs[0] - lows[i]) / highs[0] if highs[0] != 0 else 0
                if h_diff >= threshold:
                    mode = "peak"
                    last_extreme_idx = i
                elif l_diff >= threshold:
                    mode = "trough"
                    last_extreme_idx = i
            else:
                if mode == "peak":
                    # 寻找新高，或者如果跌破最高点一定比例，确立当前为Peak，转为寻找Trough
                    if highs[i] > highs[last_extreme_idx]:
                        last_extreme_idx = i
                    elif (highs[last_extreme_idx] - lows[i]) / highs[
                        last_extreme_idx
                    ] >= threshold:
                        swings.append(
                            SwingPoint(
                                index=last_extreme_idx,
                                type="peak",
                                price=float(highs[last_extreme_idx]),
                                date_str=str(dates[last_extreme_idx]),
                            )
                        )
                        mode = "trough"
                        last_extreme_idx = i
                elif mode == "trough":
                    # 寻找新低，或者如果突破最低点一定比例，确立当前为Trough，转为寻找Peak
                    if lows[i] < lows[last_extreme_idx]:
                        last_extreme_idx = i
                    elif (highs[i] - lows[last_extreme_idx]) / lows[
                        last_extreme_idx
                    ] >= threshold:
                        swings.append(
                            SwingPoint(
                                index=last_extreme_idx,
                                type="trough",
                                price=float(lows[last_extreme_idx]),
                                date_str=str(dates[last_extreme_idx]),
                            )
                        )
                        mode = "peak"
                        last_extreme_idx = i

        # 加入最后一个极值点
        if mode == "peak" and last_extreme_idx < len(df):
            swings.append(
                SwingPoint(
                    index=last_extreme_idx,
                    type="peak",
                    price=float(highs[last_extreme_idx]),
                    date_str=str(dates[last_extreme_idx]),
                )
            )
        elif mode == "trough" and last_extreme_idx < len(df):
            swings.append(
                SwingPoint(
                    index=last_extreme_idx,
                    type="trough",
                    price=float(lows[last_extreme_idx]),
                    date_str=str(dates[last_extreme_idx]),
                )
            )

        # 始终把最后一个K线点作为 current 点（连接当前最新价格）
        if swings and swings[-1].index != len(df) - 1:
            swings.append(
                SwingPoint(
                    index=len(df) - 1,
                    type="current",
                    price=float(df.iloc[-1]["close"]),
                    date_str=str(dates[-1]),
                )
            )

        return swings

    @staticmethod
    def analyze(
        df: pd.DataFrame, threshold: float = WAVE_ZIGZAG_THRESHOLD
    ) -> Optional[WaveAnalysisResult]:
        """
        进行波浪和斐波那契综合分析
        """
        if df.empty or len(df) < WAVE_MIN_K_COUNT:
            app_logger.warning("数据量不足，无法进行波浪分析")
            return None

        # 1. 检测极值点
        swings = WaveAnalyzer.detect_zigzag(df, threshold)
        if len(swings) < 3:
            return None

        # 2. 判断当前处于哪个浪形结构
        current_wave = WaveAnalyzer._identify_current_wave(swings, df.iloc[-1]["close"])

        # 3. 计算最近波段的斐波那契回撤与延伸位
        fib_levels = WaveAnalyzer._calculate_fibonacci(swings)

        return WaveAnalysisResult(
            df=df,
            swings=swings,
            current_wave=current_wave,
            fib_levels=fib_levels,
            all_waves=[],
        )

    @staticmethod
    def _identify_current_wave(
        swings: list[SwingPoint], current_price: float
    ) -> dict[str, Any]:
        """
        根据摆动点序列，识别当前的浪型位置。
        返回格式: {
            "wave": "3" | "4" | "5" | "A" | "B" | "C" | "unknown",
            "trend": "bullish" | "bearish",
            "desc": str,
            "confidence": float
        }
        """
        # 只保留真正的极值点（排除最后的 current 标志）
        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 3:
            return {
                "wave": "unknown",
                "trend": "bullish",
                "desc": "数据不足以确立波浪结构",
                "confidence": 0.3,
            }

        # 我们主要从最近的 3~5 个极值点来做结构拟合
        # 设最近的五个端点为 P4, P3, P2, P1, P0 (P0是最近的，P4是较早的)
        # 为方便理解，我们倒数：e_last[-1] 为最近的极值点
        e_last = extremes[-5:] if len(extremes) >= 5 else extremes

        n = len(e_last)

        # 1. 尝试判断是否是上升五浪（牛市推动浪）
        # 五个点：e[-5](低点) -> e[-4](高点) -> e[-3](低点) -> e[-2](高点) -> e[-1](低点)
        # 或者 e[-5](高) -> ...
        if n >= 4:
            # 判断最近4个点的走势
            p3, p2, p1, p0 = e_last[-4:]

            # 情况 A：p3(低) -> p2(高) -> p1(低) -> p0(高) —— 上升浪结构
            if (
                p3.type == "trough"
                and p2.type == "peak"
                and p1.type == "trough"
                and p0.type == "peak"
            ):
                w1_len = p2.price - p3.price
                # w2_len = p2.price - p1.price  # noqa: F841
                # w3_len = p0.price - p1.price  # noqa: F841

                # 规则验证：
                # 浪1为正，浪2回调不破浪1起点，浪3高点超过浪1高点
                if w1_len > 0 and p1.price > p3.price and p0.price > p2.price:
                    # 如果当前价格在 p0.price 以下，说明可能处于 浪4 回调中
                    if current_price < p0.price:
                        # 浪4 低点通常不应低于浪1高点(p2.price)
                        overlap_viol = current_price < p2.price
                        conf = 0.6 if overlap_viol else 0.85
                        desc = (
                            "可能处于第4浪调整中"
                            if not overlap_viol
                            else "可能处于第4浪调整（有重叠警告）"
                        )
                        return {
                            "wave": "4",
                            "trend": "bullish",
                            "desc": desc,
                            "confidence": conf,
                        }
                    else:
                        # 当前价格创出新高，可能处于 浪3 的延伸或者已开启 浪5
                        return {
                            "wave": "5",
                            "trend": "bullish",
                            "desc": "可能处于第5浪上升拉升中",
                            "confidence": 0.8,
                        }

            # 情况 B：p3(高) -> p2(低) -> p1(high) -> p0(low) —— 下跌浪结构 / A-B-C 结构
            elif (
                p3.type == "peak"
                and p2.type == "trough"
                and p1.type == "peak"
                and p0.type == "trough"
            ):
                # 下跌五浪或者 ABC 调整浪
                # 如果 p1.price < p3.price (高点降低) 并且 p0.price < p2.price (低点降低)
                if p1.price < p3.price and p0.price < p2.price:
                    # 偏熊市或ABC中的C浪
                    if current_price > p0.price:
                        return {
                            "wave": "B",
                            "trend": "bearish",
                            "desc": "可能处于ABC调整的B浪反弹中",
                            "confidence": 0.7,
                        }
                    else:
                        return {
                            "wave": "C",
                            "trend": "bearish",
                            "desc": "可能处于C浪杀跌或下跌第5浪中",
                            "confidence": 0.8,
                        }

        # 兜底分析：如果仅有3个极值点
        if n >= 3:
            p2, p1, p0 = e_last[-3:]
            # p2(低) -> p1(高) -> p0(低)
            if p2.type == "trough" and p1.type == "peak" and p0.type == "trough":
                if p0.price > p2.price:
                    # 确立了底比底高，当前如果向上，极有可能是第3浪启动
                    if current_price > p0.price:
                        return {
                            "wave": "3",
                            "trend": "bullish",
                            "desc": "双底确立，可能正处于主升第3浪中",
                            "confidence": 0.75,
                        }
                    else:
                        return {
                            "wave": "2",
                            "trend": "bullish",
                            "desc": "可能处于第2浪底部筑底中",
                            "confidence": 0.6,
                        }
            # p2(高) -> p1(低) -> p0(高)
            elif p2.type == "peak" and p1.type == "trough" and p0.type == "peak":
                if p0.price < p2.price:
                    # 高点降低，进入调整
                    if current_price < p0.price:
                        return {
                            "wave": "A",
                            "trend": "bearish",
                            "desc": "可能正处于A浪杀跌中",
                            "confidence": 0.7,
                        }

        return {
            "wave": "1",
            "trend": "bullish",
            "desc": "当前处于常规行情的第1浪筑底/震荡中",
            "confidence": 0.5,
        }

    @staticmethod
    def _calculate_fibonacci(swings: list[SwingPoint]) -> dict[str, float]:
        """
        利用最近的一个显著波段来计算斐波那契回撤与延伸位。
        """
        # 过滤出最近的两个极值点
        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 2:
            return {}

        # 最近的波段 P1 -> P0
        p1 = extremes[-2]
        p0 = extremes[-1]

        high_val = max(p1.price, p0.price)
        low_val = min(p1.price, p0.price)
        diff = high_val - low_val

        # 回撤比率
        ratios = {
            "0.236": 0.236,
            "0.382": 0.382,
            "0.500": 0.500,
            "0.618": 0.618,
            "0.786": 0.786,
        }

        levels = {}
        # 如果最近是下跌段 (Peak -> Trough)
        if p1.price > p0.price:
            levels["start"] = p1.price
            levels["end"] = p0.price
            for name, r in ratios.items():
                levels[name] = low_val + diff * r  # 从底部反弹的阻力位
        # 如果最近是上涨段 (Trough -> Peak)
        else:
            levels["start"] = p1.price
            levels["end"] = p0.price
            for name, r in ratios.items():
                levels[name] = high_val - diff * r  # 从顶部回调的支撑位

        # 添加延伸位 (基于1.618等)
        levels["1.272"] = (
            high_val + diff * 0.272 if p1.price < p0.price else low_val - diff * 0.272
        )
        levels["1.618"] = (
            high_val + diff * 0.618 if p1.price < p0.price else low_val - diff * 0.618
        )

        return levels
