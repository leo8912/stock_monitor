"""
量化指标纯计算函数模块。

本模块集中存放从 :class:`~stock_monitor.core.engine.quant_engine.QuantEngine`
抽离出来的无状态指标计算函数。这些函数只依赖传入的 ``DataFrame``，
不访问网络、缓存或引擎实例状态，便于独立测试与复用。

注意：部分函数依赖 ``pandas_ta``（通过 ``df.ta`` 访问器），
调用前需确保 pandas-ta 已激活（由 ``QuantEngine._ensure_ta_active`` 负责）。
"""

import numpy as np
import pandas as pd

from stock_monitor.utils.logger import app_logger


def check_macd_bullish_divergence(
    df: pd.DataFrame, window: int = 30, end_idx: int = None
) -> bool:
    """检测 MACD 底背离：价格创新低而 MACD 柱不再创新低。"""
    try:
        # 复制 DataFrame 避免修改调用者的原始数据
        df = df.copy()
        if "MACDh_12_26_9" not in df.columns:
            df.ta.macd(append=True)
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < window * 2:
            return False
        cols = [c for c in df.columns if c.startswith("MACDh_")]
        if not cols:
            return False
        m_col = cols[0]
        recent = curr.iloc[-window:]
        prev = curr.iloc[-window * 2 : -window]
        ri = recent["close"].idxmin()
        pi = prev["close"].idxmin()
        if (
            recent.loc[ri, "close"] < prev.loc[pi, "close"]
            and recent.loc[ri, m_col] > prev.loc[pi, m_col]
        ):
            if ri >= curr.index[-5]:
                return True
        return False
    except Exception as e:
        app_logger.debug(f"MACD底背离检测异常: {e}")
        return False


def check_bbands_squeeze(df: pd.DataFrame, end_idx: int = None) -> bool:
    """检测布林带收窄（变盘前兆）：当前带宽接近近 100 根最小带宽。"""
    try:
        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 100:
            return False
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
        if rsi > 70:
            res["strength"] = "🔥 极强/超买"
        elif rsi < 30:
            res["strength"] = "❄️ 极弱/超卖"
        else:
            res["strength"] = f"⚡ 强弱度:{rsi:.0f}"

        # 3. 成交量脉冲 (Volume Pulse)
        vol_avg20 = df["volume"].rolling(20).mean().iloc[-1]
        vol_curr = df["volume"].iloc[-1]
        if vol_curr > vol_avg20 * 2.0:
            res["pulse"] = f"🚀 异常放量 (x{vol_curr / vol_avg20:.1f})"

        return res
    except Exception as e:
        app_logger.warning(f"指标计算异常: {e}")
        return {}
