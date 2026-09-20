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
    def __init__(self, index: int, type: str, price: float, date_str: str) -> None:
        """初始化摆动点。

        Args:
            index: 该点在 K 线序列中的下标。
            type: 类型，'peak'（高点）/ 'trough'（低点）/ 'current'（最新点）。
            price: 价格。
            date_str: 日期字符串。
        """
        self.index = index
        self.type = type  # 'peak' (高点) or 'trough' (低点) or 'current' (最新点)
        self.price = price
        self.date_str = date_str
        try:
            self.datetime = pd.Timestamp(date_str)
        except Exception:
            self.datetime = pd.NaT

    def to_dict(self) -> dict[str, Any]:
        """将摆动点转换为字典形式（index/type/price/date）。"""
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
    ) -> None:
        """初始化波浪分析结果容器。

        Args:
            df: 用于分析的 K 线数据。
            swings: ZigZag 摆动点列表。
            current_wave: 当前浪型识别结果。
            fib_levels: 斐波那契回撤/延伸位。
            all_waves: 各浪段的时间与空间明细。
            remaining_space: 当前浪剩余空间预估（可选）。
        """
        self.df = df
        self.swings = swings
        self.current_wave = current_wave
        self.fib_levels = fib_levels
        self.all_waves = all_waves
        self.remaining_space = remaining_space


class WaveAnalyzer:
    """波浪理论与斐波那契计算分析器"""

    @staticmethod
    def _make_zigzag_point(idx: int, kind: str, price: float, dates) -> SwingPoint:
        """构造一个 ZigZag 摆动点。"""
        return SwingPoint(
            index=idx,
            type=kind,
            price=float(price),
            date_str=str(dates[idx]),
        )

    @staticmethod
    def _zigzag_bootstrap_step(
        highs, lows, i: int, threshold: float
    ) -> tuple[str | None, int]:
        """初始阶段：寻找第一个超过阈值的波动方向，返回 (mode, 极值索引)。"""
        h_diff = (highs[i] - lows[0]) / lows[0] if lows[0] != 0 else 0
        l_diff = (highs[0] - lows[i]) / highs[0] if highs[0] != 0 else 0
        if h_diff >= threshold:
            return "peak", i
        if l_diff >= threshold:
            return "trough", i
        return None, 0

    @staticmethod
    def _zigzag_extend_step(
        swings: list[SwingPoint],
        highs,
        lows,
        dates,
        i: int,
        mode: str,
        last_extreme_idx: int,
        threshold: float,
    ) -> tuple[str, int]:
        """延续阶段：更新极值或确认转折并追加摆动点，返回 (mode, 极值索引)。"""
        if mode == "peak":
            # 寻找新高，或跌破最高点一定比例则确认 Peak，转为寻找 Trough
            if highs[i] > highs[last_extreme_idx]:
                return "peak", i
            if (highs[last_extreme_idx] - lows[i]) / highs[
                last_extreme_idx
            ] >= threshold:
                swings.append(
                    WaveAnalyzer._make_zigzag_point(
                        last_extreme_idx, "peak", highs[last_extreme_idx], dates
                    )
                )
                return "trough", i
            return "peak", last_extreme_idx
        # mode == "trough"
        # 寻找新低，或突破最低点一定比例则确认 Trough，转为寻找 Peak
        if lows[i] < lows[last_extreme_idx]:
            return "trough", i
        if (highs[i] - lows[last_extreme_idx]) / lows[last_extreme_idx] >= threshold:
            swings.append(
                WaveAnalyzer._make_zigzag_point(
                    last_extreme_idx, "trough", lows[last_extreme_idx], dates
                )
            )
            return "peak", i
        return "trough", last_extreme_idx

    @staticmethod
    def _zigzag_append_final(
        swings: list[SwingPoint],
        highs,
        lows,
        dates,
        mode: str | None,
        last_extreme_idx: int,
        n_bars: int,
    ) -> None:
        """把最后一个尚未入库的极值点补入摆动序列。"""
        if mode == "peak" and last_extreme_idx < n_bars:
            swings.append(
                WaveAnalyzer._make_zigzag_point(
                    last_extreme_idx, "peak", highs[last_extreme_idx], dates
                )
            )
        elif mode == "trough" and last_extreme_idx < n_bars:
            swings.append(
                WaveAnalyzer._make_zigzag_point(
                    last_extreme_idx, "trough", lows[last_extreme_idx], dates
                )
            )

    @staticmethod
    def _zigzag_append_current(swings: list[SwingPoint], df, dates) -> None:
        """始终把最后一根 K 线作为 current 点，连接最新价格。"""
        if swings and swings[-1].index != len(df) - 1:
            swings.append(
                WaveAnalyzer._make_zigzag_point(
                    len(df) - 1, "current", float(df.iloc[-1]["close"]), dates
                )
            )

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
                mode, last_extreme_idx = WaveAnalyzer._zigzag_bootstrap_step(
                    highs, lows, i, threshold
                )
            else:
                mode, last_extreme_idx = WaveAnalyzer._zigzag_extend_step(
                    swings, highs, lows, dates, i, mode, last_extreme_idx, threshold
                )

        # 加入最后一个极值点
        WaveAnalyzer._zigzag_append_final(
            swings, highs, lows, dates, mode, last_extreme_idx, len(df)
        )

        # 始终把最后一个K线点作为 current 点（连接当前最新价格）
        WaveAnalyzer._zigzag_append_current(swings, df, dates)

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
    def _assess_global_downtrend(extremes: list[SwingPoint]) -> bool:
        """综合高低点变化判断是否处于全局下跌趋势。"""
        all_peaks = [s for s in extremes if s.type == "peak"]
        all_troughs = [s for s in extremes if s.type == "trough"]

        is_global_downtrend = False
        if len(all_peaks) >= 2:
            recent_high = all_peaks[-1].price
            prev_high = all_peaks[-2].price
            if recent_high < prev_high * GLOBAL_TREND_THRESHOLD:
                is_global_downtrend = True
        if len(all_troughs) >= 2:
            recent_low = all_troughs[-1].price
            prev_low = all_troughs[-2].price
            if recent_low < prev_low:
                is_global_downtrend = True
        return is_global_downtrend

    @staticmethod
    def _four_point_up(
        p3: SwingPoint,
        p2: SwingPoint,
        p1: SwingPoint,
        p0: SwingPoint,
        current_price: float,
    ) -> dict[str, Any] | None:
        """低→高→低→高（上升结构）的四点浪型判定，非该结构返回 None。"""
        w1 = p2.price - p3.price  # 浪1幅度
        w3 = p0.price - p1.price  # 浪3幅度
        if w1 <= 0:
            return None  # 无效结构

        # Elliott 铁律验证
        rules_ok = True
        rule_notes = []
        if p1.price < p3.price:
            rules_ok = False
            rule_notes.append("浪2跌破浪1起点")
        if w3 < w1 and w3 < (p2.price - p0.price if p0.price < p2.price else 0):
            rules_ok = False
            rule_notes.append("浪3为最短浪")
        if current_price < p2.price and current_price < p0.price:
            rule_notes.append("浪4与浪1有重叠")

        if p0.price <= p2.price:
            return None

        rule_check = "；".join(rule_notes) if rule_notes else "符合Elliott规则"
        if current_price < p0.price:
            # 价格从浪5高点回落
            return {
                "wave": "4",
                "trend": "bullish",
                "desc": "上涨趋势中的回调阶段",
                "confidence": 0.85 if rules_ok else 0.55,
                "rule_check": rule_check,
            }
        return {
            "wave": "5",
            "trend": "bullish",
            "desc": "上涨趋势的最后拉升阶段",
            "confidence": 0.8 if rules_ok else 0.5,
            "rule_check": rule_check,
        }

    @staticmethod
    def _four_point_down(
        p3: SwingPoint,
        p2: SwingPoint,
        p1: SwingPoint,
        p0: SwingPoint,
        current_price: float,
    ) -> dict[str, Any] | None:
        """高→低→高→低（下跌结构）的四点浪型判定，非该结构返回 None。"""
        if not (p1.price < p3.price and p0.price < p2.price):
            return None
        if current_price > p0.price:
            return {
                "wave": "B",
                "trend": "bearish",
                "desc": "下跌趋势中的反弹阶段",
                "confidence": 0.7,
                "rule_check": "高点降低，低点降低，下跌趋势确认",
            }
        return {
            "wave": "C",
            "trend": "bearish",
            "desc": "下跌趋势的加速杀跌阶段",
            "confidence": 0.8,
            "rule_check": "高点降低，低点降低，下跌趋势确认",
        }

    @staticmethod
    def _identify_from_four_points(
        quad: list[SwingPoint], current_price: float
    ) -> dict[str, Any] | None:
        """基于最近 4 个极值点识别浪型，无匹配结构返回 None。"""
        p3, p2, p1, p0 = quad
        is_up = (
            p3.type == "trough"
            and p2.type == "peak"
            and p1.type == "trough"
            and p0.type == "peak"
        )
        if is_up:
            return WaveAnalyzer._four_point_up(p3, p2, p1, p0, current_price)

        is_down = (
            p3.type == "peak"
            and p2.type == "trough"
            and p1.type == "peak"
            and p0.type == "trough"
        )
        if is_down:
            return WaveAnalyzer._four_point_down(p3, p2, p1, p0, current_price)
        return None

    @staticmethod
    def _three_point_low_high_low(
        tri: list[SwingPoint], current_price: float, is_global_downtrend: bool
    ) -> dict[str, Any] | None:
        """低→高→低（3 点）结构判定，非该结构返回 None。"""
        p2, p1, p0 = tri
        if p0.price <= p2.price:
            return None
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
            return {
                "wave": "A",
                "trend": "bearish",
                "desc": "反弹结束，继续调整",
                "confidence": 0.6,
                "rule_check": "全局下跌趋势，反弹后回落",
            }
        # 全局偏多 + 底比底高 = 可能是第3浪
        if current_price > p0.price:
            return {
                "wave": "3",
                "trend": "bullish",
                "desc": "底部抬高，可能进入上涨阶段",
                "confidence": 0.7,
                "rule_check": "底比底高，趋势转多",
            }
        return {
            "wave": "2",
            "trend": "bullish",
            "desc": "上涨后的回踩确认阶段",
            "confidence": 0.55,
            "rule_check": "底比底高但价格仍弱",
        }

    @staticmethod
    def _three_point_high_low_high(
        tri: list[SwingPoint], current_price: float, is_global_downtrend: bool
    ) -> dict[str, Any] | None:
        """高→低→高（3 点）结构判定，非该结构返回 None。"""
        p2, p1, p0 = tri
        if p0.price >= p2.price:
            return None
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
            return {
                "wave": "B",
                "trend": "bearish",
                "desc": "下跌趋势中的反弹阶段",
                "confidence": 0.65,
                "rule_check": "高点降低，下跌趋势中的反弹",
            }
        # 只是正常回调
        if current_price < p0.price:
            return {
                "wave": "4",
                "trend": "bullish",
                "desc": "上涨趋势中的回调阶段",
                "confidence": 0.6,
                "rule_check": "高点略降，正常回调",
            }
        return None

    @staticmethod
    def _identify_from_three_points(
        tri: list[SwingPoint], current_price: float, is_global_downtrend: bool
    ) -> dict[str, Any] | None:
        """基于最近 3 个极值点识别浪型，无匹配结构返回 None。"""
        p2, p1, p0 = tri
        if p2.type == "trough" and p1.type == "peak" and p0.type == "trough":
            return WaveAnalyzer._three_point_low_high_low(
                tri, current_price, is_global_downtrend
            )
        if p2.type == "peak" and p1.type == "trough" and p0.type == "peak":
            return WaveAnalyzer._three_point_high_low_high(
                tri, current_price, is_global_downtrend
            )
        return None

    @staticmethod
    def _fallback_wave(
        extremes: list[SwingPoint], current_price: float, is_global_downtrend: bool
    ) -> dict[str, Any]:
        """兜底：用全局趋势对无法匹配结构的行情做最终判断。"""
        all_troughs = [s for s in extremes if s.type == "trough"]
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

        is_global_downtrend = WaveAnalyzer._assess_global_downtrend(extremes)
        e_last = extremes[-5:] if len(extremes) >= 5 else extremes

        # 优先 4 点结构分析
        if len(e_last) >= 4:
            result = WaveAnalyzer._identify_from_four_points(e_last[-4:], current_price)
            if result is not None:
                return result

        # 次选 3 点结构分析（信息较少，置信度降低）
        if len(e_last) >= 3:
            result = WaveAnalyzer._identify_from_three_points(
                e_last[-3:], current_price, is_global_downtrend
            )
            if result is not None:
                return result

        # 兜底：用全局趋势做最终判断
        return WaveAnalyzer._fallback_wave(extremes, current_price, is_global_downtrend)

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
    def _collect_up_segments(extremes: list[SwingPoint]) -> list[float]:
        """收集所有 trough→peak 上升段的幅度列表。"""
        up_segments = []
        for i in range(len(extremes) - 1):
            if extremes[i].type == "trough" and extremes[i + 1].type == "peak":
                up_segments.append(extremes[i + 1].price - extremes[i].price)
        return up_segments

    @staticmethod
    def _collect_down_segments(extremes: list[SwingPoint]) -> list[float]:
        """收集所有 peak→trough 下跌段的幅度列表。"""
        down_segments = []
        for i in range(len(extremes) - 1):
            if extremes[i].type == "peak" and extremes[i + 1].type == "trough":
                down_segments.append(extremes[i].price - extremes[i + 1].price)
        return down_segments

    @staticmethod
    def _last_price_of(extremes: list[SwingPoint], kind: str) -> float | None:
        """返回指定类型（peak/trough）最近一个极值的价格，无则 None。"""
        points = [s for s in extremes if s.type == kind]
        return points[-1].price if points else None

    @staticmethod
    def _resolve_current_price(
        swings: list[SwingPoint], actual_current_price: float | None
    ) -> float:
        """解析用于估算的当前价：优先显式传入，其次取最后一个摆动点价格。"""
        if actual_current_price is not None:
            return actual_current_price
        return swings[-1].price if swings else 0

    @staticmethod
    def _resolve_estimate_inputs(
        swings: list[SwingPoint],
        current_wave: dict[str, Any],
        actual_current_price: float | None,
    ) -> tuple[str, str, list[SwingPoint], float] | None:
        """校验并解析估算所需输入，非法（数据不足/无价格）时返回 None。"""
        wave = current_wave.get("wave", "")
        trend = current_wave.get("trend", "")
        if not wave or wave in ("unknown", "1"):
            return None

        extremes = [s for s in swings if s.type in ("peak", "trough")]
        if len(extremes) < 2:
            return None

        curr_price = WaveAnalyzer._resolve_current_price(swings, actual_current_price)
        if curr_price <= 0:
            return None
        return wave, trend, extremes, curr_price

    @staticmethod
    def _estimate_bullish_target(
        extremes: list[SwingPoint], wave: str, curr_price: float
    ) -> tuple[float | None, str]:
        """估计上涨趋势（浪3/4/5）的目标价与计算依据。"""
        up_segments = WaveAnalyzer._collect_up_segments(extremes)

        if wave == "3" and len(up_segments) >= 1:
            # 浪3目标 = 浪1幅度 × 1.618 + 浪3起点（最近的 trough）
            w3_start = WaveAnalyzer._last_price_of(extremes, "trough")
            if w3_start is not None:
                return w3_start + up_segments[0] * 1.618, "浪1幅度×1.618"
        elif wave == "5" and len(up_segments) >= 2:
            # 浪5目标 = 浪1幅度 × 系数 + 浪4低点（衰减）
            w5_start = WaveAnalyzer._last_price_of(extremes, "trough")
            if w5_start is not None:
                coeff = FIB_TARGET_COEFFICIENTS["wave_5_target"]
                return w5_start + up_segments[0] * coeff, f"浪1幅度×{coeff}（衰减）"
        elif wave == "4" and len(up_segments) >= 1:
            # 浪4回调目标 = 浪3幅度 × 系数
            coeff = FIB_TARGET_COEFFICIENTS["wave_4_retrace"]
            return curr_price - up_segments[-1] * coeff, f"浪3幅度×{coeff}回调"
        return None, ""

    @staticmethod
    def _estimate_bearish_target(
        extremes: list[SwingPoint], wave: str
    ) -> tuple[float | None, str]:
        """估计下跌趋势（浪A/B/C）的目标价与计算依据。"""
        down_segments = WaveAnalyzer._collect_down_segments(extremes)

        if wave == "C" and len(down_segments) >= 1:
            # C浪目标 = 浪B高点 - 浪A幅度（等长）
            w_b_end = WaveAnalyzer._last_price_of(extremes, "peak")
            if w_b_end is not None:
                return w_b_end - down_segments[0], "浪A幅度等长"
        elif wave == "B" and down_segments:
            # B浪反弹通常回撤浪A的一定系数
            w_b_start = WaveAnalyzer._last_price_of(extremes, "peak")
            if w_b_start is not None:
                coeff = FIB_TARGET_COEFFICIENTS["wave_b_retrace"]
                return w_b_start + down_segments[0] * coeff, f"浪A幅度×{coeff}反弹"
        return None, ""

    @staticmethod
    def _estimate_avg_days(swings: list[SwingPoint]) -> int:
        """基于历史浪平均持续天数估计剩余天数，无数据时返回默认值 20。"""
        avg_days = 20  # 默认
        details = WaveAnalyzer._calculate_wave_details(swings)
        if details:
            durations = [d["duration_days"] for d in details if d["duration_days"] > 0]
            if durations:
                avg_days = int(sum(durations) / len(durations))
        return avg_days

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
        inputs = WaveAnalyzer._resolve_estimate_inputs(
            swings, current_wave, actual_current_price
        )
        if inputs is None:
            return None
        wave, trend, extremes, curr_price = inputs

        target_price = None
        basis = ""

        # 上涨趋势中的浪
        if trend == "bullish" and wave in ("3", "4", "5"):
            target_price, basis = WaveAnalyzer._estimate_bullish_target(
                extremes, wave, curr_price
            )
        # 下跌趋势中的浪
        elif trend == "bearish" and wave in ("A", "B", "C"):
            target_price, basis = WaveAnalyzer._estimate_bearish_target(extremes, wave)

        if target_price is None or target_price <= 0:
            return None

        remaining_pct = (
            (target_price - curr_price) / curr_price * 100 if curr_price else 0.0
        )

        return {
            "target_price": target_price,
            "remaining_pct": remaining_pct,
            "remaining_days_est": WaveAnalyzer._estimate_avg_days(swings),
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
