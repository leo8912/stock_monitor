"""
波浪理论与斐波那契数列分析引擎
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ...utils.logger import app_logger
from .quant_engine_constants import (
    FIB_TARGET_COEFFICIENTS,
    FIBONACCI_RATIOS,
    GLOBAL_TREND_THRESHOLD,
    WAVE_MIN_K_COUNT,
    WAVE_ZIGZAG_THRESHOLD,
)


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
    ) -> WaveAnalysisResult | None:
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

        # 5. 预估当前浪的剩余空间（传入实际当前收盘价）
        actual_price = float(df.iloc[-1]["close"])
        remaining_space = WaveAnalyzer._estimate_remaining_space(
            swings, current_wave, fib_levels, actual_current_price=actual_price
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

        # ── 全局趋势判断 ──────────────────────────────────────────
        # 检查是否存在大级别顶部/底部，避免只看局部而忽略全局
        all_peaks = [s for s in extremes if s.type == "peak"]
        all_troughs = [s for s in extremes if s.type == "trough"]

        is_global_downtrend = False

        # 高点降低 → 下跌趋势
        if len(all_peaks) >= 2:
            recent_high = all_peaks[-1].price
            prev_high = all_peaks[-2].price
            if (
                recent_high < prev_high * GLOBAL_TREND_THRESHOLD
            ):  # 近期高点比前高点低 8% 以上
                is_global_downtrend = True

        # 低点降低 → 下跌趋势
        if len(all_troughs) >= 2:
            recent_low = all_troughs[-1].price
            prev_low = all_troughs[-2].price
            if recent_low < prev_low:
                is_global_downtrend = True

        # 高点抬高 → 上涨趋势（暂未使用，保留供后续扩展）
        # if len(all_peaks) >= 2:
        #     if all_peaks[-1].price > all_peaks[-2].price * 1.08:
        #         is_global_uptrend = True

        # 低点抬高 → 上涨趋势（用于后续分析参考）
        # if len(all_troughs) >= 2:
        #     if all_troughs[-1].price > all_troughs[-2].price:
        #         is_global_uptrend = True

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
                    # 底比底高 — 但需要结合全局趋势判断
                    if is_global_downtrend:
                        # 全局下跌 + 局部底比底高 = B浪反弹，不是第3浪
                        if current_price > p0.price:
                            return {
                                "wave": "B",
                                "trend": "bearish",
                                "desc": "下跌趋势中的反弹，高度有限",
                                "confidence": 0.65,
                                "rule_check": "全局高点降低，局部反弹非新升浪",
                            }
                        else:
                            return {
                                "wave": "A",
                                "trend": "bearish",
                                "desc": "反弹结束，继续调整",
                                "confidence": 0.6,
                                "rule_check": "全局下跌趋势，反弹后回落",
                            }
                    else:
                        # 全局偏多 + 底比底高 = 可能是第3浪
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
                    # 高点降低 — 结合全局趋势
                    if is_global_downtrend or p0.price < p2.price * 0.92:
                        # 明确的下跌趋势
                        if current_price < p0.price:
                            return {
                                "wave": "C",
                                "trend": "bearish",
                                "desc": "下跌趋势的加速杀跌阶段",
                                "confidence": 0.75,
                                "rule_check": "高点降低，下跌趋势确认",
                            }
                        else:
                            return {
                                "wave": "B",
                                "trend": "bearish",
                                "desc": "下跌趋势中的反弹阶段",
                                "confidence": 0.65,
                                "rule_check": "高点降低，下跌趋势中的反弹",
                            }
                    else:
                        # 只是正常回调
                        if current_price < p0.price:
                            return {
                                "wave": "4",
                                "trend": "bullish",
                                "desc": "上涨趋势中的回调阶段",
                                "confidence": 0.6,
                                "rule_check": "高点略降，正常回调",
                            }

        # ── 兜底：用全局趋势做最终判断 ──────────────────────────
        if is_global_downtrend:
            # 如果价格在最近低点附近或以下 → C浪杀跌
            if all_troughs and current_price <= all_troughs[-1].price * 1.02:
                return {
                    "wave": "C",
                    "trend": "bearish",
                    "desc": "下跌趋势中，持续探底",
                    "confidence": 0.55,
                    "rule_check": "全局下跌趋势",
                }
            else:
                return {
                    "wave": "B",
                    "trend": "bearish",
                    "desc": "下跌趋势中的反弹阶段",
                    "confidence": 0.5,
                    "rule_check": "全局下跌趋势，当前为反弹",
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

        # 使用配置的斐波那契比率
        ratios = FIBONACCI_RATIOS.copy()

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
        计算最近几段浪的时间和空间信息。
        只返回最近 max_segments 段，避免数据过多。
        返回: [
            {
                "label": "升",  or "降"
                "from_date": "2026-03-10",
                "to_date": "2026-04-15",
                "duration_days": 26,
                "from_price": 1800.0,
                "to_price": 1950.0,
                "price_change": 150.0,
                "pct_change": 8.33,
                "direction": "up",
                "is_current": False,
            },
            ...
        ]
        """
        max_segments = 6

        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 2:
            return []

        # 只取最近的 max_segments+1 个极值点（产生 max_segments 段）
        recent = (
            extremes[-(max_segments + 1) :]
            if len(extremes) > max_segments + 1
            else extremes
        )

        details = []
        up_count = 0
        down_count = 0

        for i in range(len(recent) - 1):
            p_from = recent[i]
            p_to = recent[i + 1]

            duration_days = 0
            if not pd.isna(p_from.datetime) and not pd.isna(p_to.datetime):
                delta = p_to.datetime - p_from.datetime
                duration_days = max(int(delta.days), 1)

            price_change = p_to.price - p_from.price
            pct_change = (price_change / p_from.price * 100) if p_from.price != 0 else 0
            direction = "up" if price_change >= 0 else "down"

            if direction == "up":
                up_count += 1
                label = f"升{up_count}"
            else:
                down_count += 1
                label = f"降{down_count}"

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
                    "is_current": False,
                }
            )

        # 最后一段标记为"当前"
        if details:
            details[-1]["is_current"] = True

        return details

    @staticmethod
    def _estimate_remaining_space(
        swings: list[SwingPoint],
        current_wave: dict[str, Any],
        fib_levels: dict[str, float],
        actual_current_price: float | None = None,
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

        # 使用实际当前价（收盘价），而非最后一个摆动点价格
        curr_price = (
            actual_current_price
            if actual_current_price is not None
            else (swings[-1].price if swings else 0)
        )
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
                # 浪5目标 = 浪1幅度 × 系数 + 浪4低点（衰减）
                w1_amp = up_segments[0]
                last_troughs = [s for s in extremes if s.type == "trough"]
                if len(last_troughs) >= 1:
                    w5_start = last_troughs[-1].price
                    coeff = FIB_TARGET_COEFFICIENTS["wave_5_target"]
                    target_price = w5_start + w1_amp * coeff
                    basis = f"浪1幅度×{coeff}（衰减）"

            elif wave == "4":
                # 浪4回调目标 = 浪3幅度 × 系数
                if len(up_segments) >= 1:
                    w3_amp = up_segments[-1]
                    coeff = FIB_TARGET_COEFFICIENTS["wave_4_retrace"]
                    target_price = curr_price - w3_amp * coeff
                    basis = f"浪3幅度×{coeff}回调"

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
                # B浪反弹通常回撤 A浪的 系数
                if down_segments:
                    w_a_amp = down_segments[0]
                    last_peaks = [s for s in extremes if s.type == "peak"]
                    if last_peaks:
                        w_b_start = last_peaks[-1].price
                        coeff = FIB_TARGET_COEFFICIENTS["wave_b_retrace"]
                        target_price = w_b_start + w_a_amp * coeff
                        basis = f"浪A幅度×{coeff}反弹"

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


def explain_wave(wave: str, trend: str) -> str:
    """
    解释当前波浪阶段的含义

    Args:
        wave: 波浪标识 (1-5, A, B, C)
        trend: 趋势方向 (bullish, bearish)

    Returns:
        波浪阶段的中文解释
    """
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


def wave_hint(wave: str, trend: str) -> str:
    """
    根据波浪阶段给出操作建议

    Args:
        wave: 波浪标识 (1-5, A, B, C)
        trend: 趋势方向 (bullish, bearish)

    Returns:
        操作建议文本
    """
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


def analyze_and_record(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str = "daily",
    threshold: float = WAVE_ZIGZAG_THRESHOLD,
    record_prediction: bool = True,
    fib_coefficients: dict | None = None,
) -> WaveAnalysisResult | None:
    """
    进行波浪分析并记录预测

    Args:
        df: K线数据
        symbol: 股票代码
        timeframe: 时间周期
        threshold: ZigZag阈值
        record_prediction: 是否记录预测
        fib_coefficients: 自定义斐波那契系数 (可选)

    Returns:
        WaveAnalysisResult or None
    """
    # 如果提供了自定义系数，更新全局系数
    if fib_coefficients:
        for key, value in fib_coefficients.items():
            if key in FIB_TARGET_COEFFICIENTS:
                FIB_TARGET_COEFFICIENTS[key] = value

    result = WaveAnalyzer.analyze(df, threshold)

    if result and record_prediction and result.current_wave:
        wave = result.current_wave.get("wave", "unknown")
        trend = result.current_wave.get("trend", "bullish")
        confidence = result.current_wave.get("confidence", 0)
        current_price = float(df.iloc[-1]["close"])

        # 获取目标价格
        target_price = None
        if result.remaining_space:
            target_price = result.remaining_space.get("target_price")

        # 记录预测
        try:
            from ...services.wave_prediction_service import wave_prediction_service

            wave_prediction_service.record_prediction(
                symbol=symbol,
                wave=wave,
                trend=trend,
                confidence=confidence,
                price_at_prediction=current_price,
                target_price=target_price,
                timeframe=timeframe,
                notes=f"自动记录: {explain_wave(wave, trend)}",
            )
        except Exception as e:
            app_logger.debug(f"[波浪预测] 记录预测失败（非致命）: {e}")

    return result
