"""
量化指标纯计算函数模块。

本模块集中存放从 :class:`~stock_monitor.core.engine.quant_engine.QuantEngine`
抽离出来的无状态指标计算函数。这些函数只依赖传入的 ``DataFrame``，
不访问网络、缓存或引擎实例状态，便于独立测试与复用。

注意：部分函数依赖 ``pandas_ta``（通过 ``df.ta`` 访问器），
调用前需确保 pandas-ta 已激活（由 ``QuantEngine._ensure_ta_active`` 负责）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stock_monitor.utils.logger import app_logger


def check_macd_bullish_divergence(
    df: pd.DataFrame, window: int = 30, end_idx: int = None
) -> bool:
    """检测 MACD 底背离：价格创新低而 MACD 柱不再创新低。"""
    detail = describe_macd_divergence(df, window=window, end_idx=end_idx, top=False)
    return detail is not None


def check_macd_bearish_divergence(
    df: pd.DataFrame, window: int = 30, end_idx: int = None
) -> bool:
    """检测 MACD 顶背离：价格创新高而 MACD 柱不再创新高（离场信号）。"""
    detail = describe_macd_divergence(df, window=window, end_idx=end_idx, top=True)
    return detail is not None


def describe_macd_divergence(
    df: pd.DataFrame, window: int = 30, end_idx: int = None, top: bool = False
) -> dict | None:
    """量化 MACD 背离，返回背离详情字典；未发生背离或数据不足返回 None。

    Args:
        df: K 线数据（需含 close 列）。
        window: 对比窗口（默认 30 根，与历史检测一致）。
        end_idx: 截止行索引（回测逐点调用时传入）。
        top: False 检测底背离（低点对比），True 检测顶背离（高点对比）。

    Returns:
        ``{"price_a", "price_b", "price_change_pct", "hist_a", "hist_b",
        "hist_change_pct"}``；底背离为价格新低+柱抬升，顶背离为价格新高+柱回落。
    """
    try:
        # 复制 DataFrame 避免修改调用者的原始数据
        df = df.copy()
        if "MACDh_12_26_9" not in df.columns:
            df.ta.macd(append=True)
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < window * 2:
            return None
        cols = [c for c in df.columns if c.startswith("MACDh_")]
        if not cols:
            return None
        m_col = cols[0]
        recent = curr.iloc[-window:]
        prev = curr.iloc[-window * 2 : -window]
        if top:
            ri = recent["close"].idxmax()
            pi = prev["close"].idxmax()
            price_ok = recent.loc[ri, "close"] > prev.loc[pi, "close"]
            hist_ok = recent.loc[ri, m_col] < prev.loc[pi, m_col]
            latest_ok = ri >= curr.index[-5]
        else:
            ri = recent["close"].idxmin()
            pi = prev["close"].idxmin()
            price_ok = recent.loc[ri, "close"] < prev.loc[pi, "close"]
            hist_ok = recent.loc[ri, m_col] > prev.loc[pi, m_col]
            latest_ok = ri >= curr.index[-5]
        if price_ok and hist_ok and latest_ok:
            price_a = float(prev.loc[pi, "close"])
            price_b = float(recent.loc[ri, "close"])
            hist_a = float(prev.loc[pi, m_col])
            hist_b = float(recent.loc[ri, m_col])
            return {
                "price_a": price_a,
                "price_b": price_b,
                "price_change_pct": (price_b - price_a) / price_a * 100
                if price_a
                else 0.0,
                "hist_a": hist_a,
                "hist_b": hist_b,
                "hist_change_pct": (hist_b - hist_a) / abs(hist_a) * 100
                if hist_a
                else 0.0,
            }
        return None
    except Exception as e:
        app_logger.debug(f"MACD背离检测异常: {e}")
        return None


def format_divergence_detail(detail: dict | None, top: bool = False) -> str:
    """把背离详情字典格式化为推送文案片段，None 返回空串。"""
    if not detail:
        return ""
    kind = "顶背离" if top else "底背离"
    hist_dir = "回落" if top else "抬升"
    return (
        f"{kind}：低点A {detail['price_a']:.2f} → 低点B {detail['price_b']:.2f}"
        f"（{detail['price_change_pct']:+.1f}%），"
        f"MACD 柱 {detail['hist_a']:.3f} → {detail['hist_b']:.3f}"
        f"（{hist_dir} {abs(detail['hist_change_pct']):.0f}%）"
    )


def check_volume_price_divergence(
    df: pd.DataFrame, lookback: int = 20, end_idx: int = None
) -> str | None:
    """检测量价背离，返回 "top" / "bottom" / None。

    - 顶背离(top)：价格创 lookback 新高，但 OBV 未创新高（派发嫌疑）。
    - 底背离(bottom)：价格创 lookback 新低、成交量萎缩，且 OBV 未创新低
      （OBV 抬升，吸筹迹象；与 check_accumulation 的低波动吸筹互补）。
    """
    try:
        df = df.copy()
        if "OBV" not in df.columns:
            df.ta.obv(append=True)
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < lookback + 5:
            return None
        win = curr.iloc[-lookback:]
        last = curr.iloc[-1]
        if last["close"] >= win["close"].max() and last["OBV"] < win["OBV"].max():
            # 价格新高要求出现在窗口末端，避免盘中历史高点误报
            if curr["close"].idxmax() == curr.index[-1]:
                return "top"
        if last["close"] <= win["close"].min():
            if curr["close"].idxmin() != curr.index[-1]:
                return None
            vol_recent = win["volume"].iloc[-5:].mean()
            vol_full = win["volume"].mean()
            if vol_recent < vol_full and last["OBV"] > win["OBV"].min():
                return "bottom"
        return None
    except Exception as e:
        app_logger.debug(f"量价背离检测异常: {e}")
        return None


def check_kdj_cross(df: pd.DataFrame, end_idx: int = None) -> str | None:
    """检测 KDJ（随机指标）金叉/死叉，返回 "golden" / "dead" / None。"""
    try:
        df = df.copy()
        k_cols = [c for c in df.columns if c.startswith("STOCHk_")]
        d_cols = [c for c in df.columns if c.startswith("STOCHd_")]
        if not k_cols or not d_cols:
            df.ta.stoch(append=True)
            k_cols = [c for c in df.columns if c.startswith("STOCHk_")]
            d_cols = [c for c in df.columns if c.startswith("STOCHd_")]
        if not k_cols or not d_cols:
            return None
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 3:
            return None
        k, d = curr[k_cols[0]], curr[d_cols[0]]
        if k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] > d.iloc[-1]:
            return "golden"
        if k.iloc[-2] >= d.iloc[-2] and k.iloc[-1] < d.iloc[-1]:
            return "dead"
        return None
    except Exception as e:
        app_logger.debug(f"KDJ 交叉检测异常: {e}")
        return None


def check_ema_cross(df: pd.DataFrame, end_idx: int = None) -> str | None:
    """检测 EMA5 上/下穿 EMA20，返回 "golden" / "dead" / None。"""
    try:
        df = df.copy()
        if "EMA_5" not in df.columns:
            df.ta.ema(length=5, append=True)
        if "EMA_20" not in df.columns:
            df.ta.ema(length=20, append=True)
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 3:
            return None
        e5, e20 = curr["EMA_5"], curr["EMA_20"]
        if e5.iloc[-2] <= e20.iloc[-2] and e5.iloc[-1] > e20.iloc[-1]:
            return "golden"
        if e5.iloc[-2] >= e20.iloc[-2] and e5.iloc[-1] < e20.iloc[-1]:
            return "dead"
        return None
    except Exception as e:
        app_logger.debug(f"均线交叉检测异常: {e}")
        return None


def check_bbands_squeeze(df: pd.DataFrame, end_idx: int = None) -> bool:
    """检测布林带收窄（变盘前兆）：当前带宽接近近 100 根最小带宽。"""
    try:
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 100:
            return False
        cols = [c for c in curr.columns if c.startswith("BBB_")]
        if not cols:
            # 调用方（扫描/对比弹窗）传入的原始 df 不含 BBB_ 列，
            # 惰性补算到副本上，避免污染调用者的 df。
            curr = curr.copy()
            curr.ta.bbands(length=20, append=True)
            cols = [c for c in curr.columns if c.startswith("BBB_")]
            if not cols:
                return False
        bw = curr[cols[0]].iloc[-1]
        return bw <= curr[cols[0]].iloc[-100:].min() * 1.05
    except Exception as e:
        app_logger.debug(f"布林带收窄检测异常: {e}")
        return False


def calculate_rsrs(df: pd.DataFrame, n: int = 18, m: int = 600) -> tuple[float, float]:
    """
    计算 RSRS (阻力支撑相对强度) 指标
    返回: (zscore, slope)
    """
    try:
        data_len = len(df)

        # 渐进式降级策略
        if data_len < n + m:
            min_required = n + max(60, m // 4)

            if data_len < min_required:
                app_logger.debug(f"RSRS 数据不足：{data_len} < {min_required}")
                return 0.0, 0.0

            adjusted_m = min(m, data_len - n)
            app_logger.info(f"RSRS 降级模式：m={m}->{adjusted_m}")
            return calculate_rsrs(df, n=n, m=adjusted_m)

        # 1. 计算斜率序列 (Slope)
        # 为了性能，只计算最近 M+1 个斜率用于标准化
        slopes = []
        highs = df["high"].values
        lows = df["low"].values

        # 使用 rolling window 计算斜率
        for i in range(len(df) - m, len(df)):
            y = highs[i - n + 1 : i + 1]
            x = lows[i - n + 1 : i + 1]
            slope = np.polyfit(x, y, 1)[0]
            slopes.append(slope)

        # 2. 标准化 (Z-Score)
        curr_slope = slopes[-1]
        history_slopes = np.array(slopes)
        mean_s = np.mean(history_slopes)
        std_s = np.std(history_slopes)

        zscore = (curr_slope - mean_s) / std_s if std_s != 0 else 0
        return round(zscore, 3), round(curr_slope, 3)
    except Exception as e:
        app_logger.warning(f"RSRS 计算失败: {e}")
        return 0.0, 0.0


def check_accumulation(df: pd.DataFrame, end_idx: int = None) -> bool:
    """检测 OBV 低位吸筹：低波动区间内 OBV 均线走强。"""
    try:
        if "OBV" not in df.columns:
            df.ta.obv(append=True)
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 20:
            return False
        r20 = curr.iloc[-20:]
        vty = (r20["high"].max() - r20["low"].min()) / (r20["low"].min() + 1e-9)
        if vty < 0.10:
            return r20["OBV"].rolling(5).mean().iloc[-1] > r20["OBV"].mean() * 1.05
        return False
    except Exception as e:
        app_logger.debug(f"OBV累积检测异常: {e}")
        return False


def get_bbands_position_desc(df: pd.DataFrame) -> str:
    """价格相对于布林带的位置，用 emoji 简洁标注"""
    try:
        # 使用浅拷贝减少内存分配（只读场景无需深拷贝）
        tmp = df.copy(deep=False)
        tmp.ta.bbands(length=20, std=2, append=True)
        bbl = [c for c in tmp.columns if c.startswith("BBL_")]
        bbu = [c for c in tmp.columns if c.startswith("BBU_")]
        bbb = [c for c in tmp.columns if c.startswith("BBB_")]
        if not bbl or not bbu:
            return " 🟡 中位震荡"
        c = tmp["close"].iloc[-1]
        lower_band = tmp[bbl[0]].iloc[-1]
        upper_band = tmp[bbu[0]].iloc[-1]
        is_sq = (
            len(tmp) >= 100
            and bbb
            and tmp[bbb[0]].iloc[-1] <= tmp[bbb[0]].iloc[-100:].min() * 1.05
        )
        sq = "-变盘" if is_sq else ""
        if c <= lower_band * 1.008:
            return f" 🟢 下轨支撑{sq}"
        elif c >= upper_band * 0.992:
            return f" 🔴 上轨阻力{sq}"
        else:
            return f" 🟡 中位震荡{sq}"
    except Exception as e:
        app_logger.debug(f"布林带位置描述异常: {e}")
        return ""


def calculate_comprehensive_indicators(df: pd.DataFrame) -> dict:
    """计算核心技术指标并返回易读的汇总，用于微信推送描述"""
    if df.empty or len(df) < 60:
        return {}
    try:
        # 复制 DataFrame 避免修改调用者的原始数据
        df = df.copy()
        res = {}
        # 1. 均线分析 (EMA5, 10, 20, 60)
        df.ta.ema(length=5, append=True)
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=60, append=True)

        c = df["close"].iloc[-1]
        e5, e10, e20, e60 = (
            df["EMA_5"].iloc[-1],
            df["EMA_10"].iloc[-1],
            df["EMA_20"].iloc[-1],
            df["EMA_60"].iloc[-1],
        )

        # 判断大趋势
        if c > e20 > e60:
            res["trend"] = "🔴 多头"
        elif c < e20 < e60:
            res["trend"] = "🟢 空头"
        else:
            res["trend"] = "🟡 震荡"

        # 压力支撑位提示
        if c > e5 > e10:
            res["support"] = f"EMA5 ({e5:.2f})"
        elif c < e5:
            res["resistance"] = f"EMA5 ({e5:.2f})"

        # 2. RSI 分析
        df.ta.rsi(length=14, append=True)
        rsi = df["RSI_14"].iloc[-1]
        res["rsi"] = float(rsi)  # 数值键：对比弹窗/推送直接读取（修复恒为 0）
        if rsi > 70:
            res["strength"] = "🔥 极强/超买"
        elif rsi < 30:
            res["strength"] = "❄️ 极弱/超卖"
        else:
            res["strength"] = f"⚡ 强弱度:{rsi:.0f}"

        # 3. 成交量脉冲 (Volume Pulse)
        vol_avg20 = df["volume"].rolling(20).mean().iloc[-1]
        vol_curr = df["volume"].iloc[-1]
        res["volume_ratio"] = float(vol_curr / vol_avg20) if vol_avg20 else 0.0
        if vol_curr > vol_avg20 * 2.0:
            res["pulse"] = f"🚀 异常放量 (x{vol_curr / vol_avg20:.1f})"

        return res
    except Exception as e:
        app_logger.warning(f"指标计算异常: {e}")
        return {}


def build_push_snapshot(df: pd.DataFrame) -> str:
    """构建微信推送用"指标快照"文本（RSI/量比/布林位置/MACD柱/支撑压力）。

    数据不足或异常时返回空串，调用方按空串跳过该区块。
    """
    try:
        if df is None or df.empty or len(df) < 60:
            return ""
        res = calculate_comprehensive_indicators(df)
        if not res:
            return ""

        parts = []
        if "rsi" in res:
            parts.append(f"RSI14 {res['rsi']:.1f}")
        if "volume_ratio" in res:
            parts.append(f"量比 {res['volume_ratio']:.2f}")

        pos = get_bbands_position_desc(df)
        if pos:
            parts.append(f"布林{pos.strip()}")

        tmp = df.copy(deep=False)
        hist_col = None
        for attempt_col in ("MACDh_12_26_9",):
            if attempt_col in tmp.columns:
                hist_col = attempt_col
                break
        if hist_col is None:
            tmp.ta.macd(append=True)
            cols = [c for c in tmp.columns if c.startswith("MACDh_")]
            hist_col = cols[0] if cols else None
        if hist_col:
            parts.append(f"MACD柱 {tmp[hist_col].iloc[-1]:+.3f}")

        if res.get("trend"):
            parts.append(f"趋势{res['trend']}")
        if res.get("support"):
            parts.append(f"支撑 {res['support']}")
        if res.get("resistance"):
            parts.append(f"压力 {res['resistance']}")
        if res.get("pulse"):
            parts.append(res["pulse"])

        if not parts:
            return ""
        return "📊 指标快照：" + " | ".join(parts)
    except Exception as e:
        app_logger.debug(f"指标快照构建异常: {e}")
        return ""
