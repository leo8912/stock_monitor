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
        try:
            self.datetime = pd.Timestamp(date_str)
        except Exception:
            self.datetime = pd.NaT

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
        remaining_space: dict[str, Any] | None = None,
    ):
        self.df = df
        self.swings = swings
        self.current_wave = current_wave
        self.fib_levels = fib_levels
        self.all_waves = all_waves
        self.remaining_space = remaining_space


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

        # 4. 计算每段浪的时间和空间
        all_waves = WaveAnalyzer._calculate_wave_details(swings)

        # 5. 预估当前浪的剩余空间
        remaining_space = WaveAnalyzer._estimate_remaining_space(
            swings, current_wave, fib_levels
        )

        return WaveAnalysisResult(
            df=df,
            swings=swings,
            current_wave=current_wave,
            fib_levels=fib_levels,
            all_waves=all_waves,
            remaining_space=remaining_space,
        )

    @staticmethod
    def _identify_current_wave(
        swings: list[SwingPoint], current_price: float
    ) -> dict[str, Any]:
        """
        根据摆动点序列，识别当前的浪型位置。
        应用 Elliott 波浪三大铁律进行验证：
          1. 浪3不能是最短的推动浪
          2. 浪4不能与浪1有价格重叠
          3. 浪2回调不能低于浪1的起点
        返回格式: {
            "wave": "1"~"5" | "A"~"C" | "unknown",
            "trend": "bullish" | "bearish",
            "desc": str,
            "confidence": float,
            "rule_check": str  # 规则验证结果
        }
        """
        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 3:
            return {
                "wave": "unknown",
                "trend": "bullish",
                "desc": "数据不足，无法判断走势结构",
                "confidence": 0.3,
                "rule_check": "",
            }

        e_last = extremes[-5:] if len(extremes) >= 5 else extremes
        n = len(e_last)

        # ── 4点结构分析 ──────────────────────────────────────────
        if n >= 4:
            p3, p2, p1, p0 = e_last[-4:]

            # 情况 A：低→高→低→高（上升结构）
            if (
                p3.type == "trough"
                and p2.type == "peak"
                and p1.type == "trough"
                and p0.type == "peak"
            ):
                w1 = p2.price - p3.price  # 浪1幅度
                w3 = p0.price - p1.price  # 浪3幅度

                if w1 <= 0:
                    pass  # 无效结构
                else:
                    # Elliott 铁律验证
                    rules_ok = True
                    rule_notes = []

                    # 规则2：浪2不破浪1起点
                    if p1.price < p3.price:
                        rules_ok = False
                        rule_notes.append("浪2跌破浪1起点")

                    # 规则1：浪3不能最短
                    if w3 < w1 and w3 < (
                        p2.price - p0.price if p0.price < p2.price else 0
                    ):
                        rules_ok = False
                        rule_notes.append("浪3为最短浪")

                    # 规则3：浪4不与浪1重叠
                    if current_price < p2.price and current_price < p0.price:
                        rule_notes.append("浪4与浪1有重叠")

                    rule_check = (
                        "；".join(rule_notes) if rule_notes else "符合Elliott规则"
                    )

                    if p0.price > p2.price:
                        # 高点抬高，确认上升推动浪
                        if current_price < p0.price:
                            # 价格从浪5高点回落
                            conf = 0.85 if rules_ok else 0.55
                            return {
                                "wave": "4",
                                "trend": "bullish",
                                "desc": "上涨趋势中的回调阶段",
                                "confidence": conf,
                                "rule_check": rule_check,
                            }
                        else:
                            return {
                                "wave": "5",
                                "trend": "bullish",
                                "desc": "上涨趋势的最后拉升阶段",
                                "confidence": 0.8 if rules_ok else 0.5,
                                "rule_check": rule_check,
                            }

            # 情况 B：高→低→高→低（下跌结构）
            elif (
                p3.type == "peak"
                and p2.type == "trough"
                and p1.type == "peak"
                and p0.type == "trough"
            ):
                if p1.price < p3.price and p0.price < p2.price:
                    # 高点降低 + 低点降低 = 确认下跌趋势
                    if current_price > p0.price:
                        return {
                            "wave": "B",
                            "trend": "bearish",
                            "desc": "下跌趋势中的反弹阶段",
                            "confidence": 0.7,
                            "rule_check": "高点降低，低点降低，下跌趋势确认",
                        }
                    else:
                        return {
                            "wave": "C",
                            "trend": "bearish",
                            "desc": "下跌趋势的加速杀跌阶段",
                            "confidence": 0.8,
                            "rule_check": "高点降低，低点降低，下跌趋势确认",
                        }

        # ── 3点结构分析（信息较少，置信度降低）────────────────────
        if n >= 3:
            p2, p1, p0 = e_last[-3:]

            if p2.type == "trough" and p1.type == "peak" and p0.type == "trough":
                if p0.price > p2.price:
                    # 底比底高 + 价格在最近低点之上 = 可能启动上涨
                    if current_price > p0.price:
                        return {
                            "wave": "3",
                            "trend": "bullish",
                            "desc": "底部抬高，可能进入上涨阶段",
                            "confidence": 0.7,
                            "rule_check": "底比底高，趋势转多",
                        }
                    else:
                        return {
                            "wave": "2",
                            "trend": "bullish",
                            "desc": "上涨后的回踩确认阶段",
                            "confidence": 0.55,
                            "rule_check": "底比底高但价格仍弱",
                        }
            elif p2.type == "peak" and p1.type == "trough" and p0.type == "peak":
                if p0.price < p2.price:
                    if current_price < p0.price:
                        return {
                            "wave": "A",
                            "trend": "bearish",
                            "desc": "上涨趋势结束，进入调整",
                            "confidence": 0.65,
                            "rule_check": "高点降低，上涨趋势可能结束",
                        }

        return {
            "wave": "1",
            "trend": "bullish",
            "desc": "震荡筑底阶段，方向待确认",
            "confidence": 0.45,
            "rule_check": "结构不明确",
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

    @staticmethod
    def _calculate_wave_details(swings: list[SwingPoint]) -> list[dict[str, Any]]:
        """
        计算每段浪的时间和空间信息。
        返回: [
            {
                "label": "浪1",
                "from_date": "2026-03-10",
                "to_date": "2026-04-15",
                "duration_days": 26,
                "from_price": 1800.0,
                "to_price": 1950.0,
                "price_change": 150.0,
                "pct_change": 8.33,
                "direction": "up",
            },
            ...
        ]
        """
        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 2:
            return []

        details = []
        wave_labels = ["浪1", "浪2", "浪3", "浪4", "浪5", "浪A", "浪B", "浪C"]
        label_idx = 0

        for i in range(len(extremes) - 1):
            p_from = extremes[i]
            p_to = extremes[i + 1]

            # 计算持续天数
            duration_days = 0
            if not pd.isna(p_from.datetime) and not pd.isna(p_to.datetime):
                delta = p_to.datetime - p_from.datetime
                duration_days = max(int(delta.days), 1)

            # 计算价格变化
            price_change = p_to.price - p_from.price
            pct_change = (price_change / p_from.price * 100) if p_from.price != 0 else 0
            direction = "up" if price_change >= 0 else "down"

            label = (
                wave_labels[label_idx]
                if label_idx < len(wave_labels)
                else f"浪{label_idx + 1}"
            )
            label_idx += 1

            details.append(
                {
                    "label": label,
                    "from_date": p_from.date_str[:10],
                    "to_date": p_to.date_str[:10],
                    "duration_days": duration_days,
                    "from_price": p_from.price,
                    "to_price": p_to.price,
                    "price_change": price_change,
                    "pct_change": pct_change,
                    "direction": direction,
                }
            )

        return details

    @staticmethod
    def _estimate_remaining_space(
        swings: list[SwingPoint],
        current_wave: dict[str, Any],
        fib_levels: dict[str, float],
    ) -> dict[str, Any] | None:
        """
        预估当前浪的剩余空间。
        基于 Elliott 波浪比例关系和 Fibonacci 延伸位。
        返回: {
            "target_price": float,
            "remaining_pct": float,
            "remaining_days_est": int,
            "basis": str,  # 计算依据
        } 或 None
        """
        wave = current_wave.get("wave", "")
        trend = current_wave.get("trend", "")
        if not wave or wave in ("unknown", "1"):
            return None

        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 2:
            return None

        curr_price = swings[-1].price if swings else 0
        if curr_price <= 0:
            return None

        target_price = None
        basis = ""

        # 上涨趋势中的浪
        if trend == "bullish" and wave in ("3", "4", "5"):
            # 找浪1的幅度（第一对 trough→peak）
            up_segments = []
            for i in range(len(extremes) - 1):
                if extremes[i].type == "trough" and extremes[i + 1].type == "peak":
                    up_segments.append(extremes[i + 1].price - extremes[i].price)

            if wave == "3" and len(up_segments) >= 1:
                # 浪3目标 = 浪1幅度 × 1.618 + 浪3起点
                w1_amp = up_segments[0]
                # 浪3起点是最近的 trough
                last_troughs = [s for s in extremes if s.type == "trough"]
                if last_troughs:
                    w3_start = last_troughs[-1].price
                    target_price = w3_start + w1_amp * 1.618
                    basis = "浪1幅度×1.618"

            elif wave == "5" and len(up_segments) >= 2:
                # 浪5目标 = 浪1幅度 × 0.618 + 浪4低点（衰减）
                w1_amp = up_segments[0]
                last_troughs = [s for s in extremes if s.type == "trough"]
                if len(last_troughs) >= 1:
                    w5_start = last_troughs[-1].price
                    target_price = w5_start + w1_amp * 0.618
                    basis = "浪1幅度×0.618（衰减）"

            elif wave == "4":
                # 浪4回调目标 = 浪3幅度 × 0.382
                if len(up_segments) >= 1:
                    w3_amp = up_segments[-1]
                    target_price = curr_price - w3_amp * 0.382
                    basis = "浪3幅度×0.382回调"

        # 下跌趋势中的浪
        elif trend == "bearish" and wave in ("A", "B", "C"):
            down_segments = []
            for i in range(len(extremes) - 1):
                if extremes[i].type == "peak" and extremes[i + 1].type == "trough":
                    down_segments.append(extremes[i].price - extremes[i + 1].price)

            if wave == "C" and len(down_segments) >= 1:
                # C浪目标 = 浪A幅度 + 浪B高点
                w_a_amp = down_segments[0]
                last_peaks = [s for s in extremes if s.type == "peak"]
                if last_peaks:
                    w_b_end = last_peaks[-1].price
                    target_price = w_b_end - w_a_amp
                    basis = "浪A幅度等长"

            elif wave == "B":
                # B浪反弹通常回撤 A浪的 0.382~0.618
                if down_segments:
                    w_a_amp = down_segments[0]
                    last_peaks = [s for s in extremes if s.type == "peak"]
                    if last_peaks:
                        w_b_start = last_peaks[-1].price
                        target_price = w_b_start + w_a_amp * 0.5
                        basis = "浪A幅度×0.5反弹"

        if target_price is None or target_price <= 0:
            return None

        remaining_pct = (target_price - curr_price) / curr_price * 100

        # 预估剩余天数：取历史浪的平均持续天数
        avg_days = 20  # 默认
        details = WaveAnalyzer._calculate_wave_details(swings)
        if details:
            durations = [d["duration_days"] for d in details if d["duration_days"] > 0]
            if durations:
                avg_days = int(sum(durations) / len(durations))

        return {
            "target_price": target_price,
            "remaining_pct": remaining_pct,
            "remaining_days_est": avg_days,
            "basis": basis,
        }
