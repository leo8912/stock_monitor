"""
量化扫描单标的信号决策纯函数。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 的
``_scan_single_symbol`` 抽离的无状态决策规则：OBV 信号格式化、
策略共振判定、优先级判定与多因子兜底信号。
"""

from __future__ import annotations

import time

from ..engine.quant_engine_constants import SIGNAL_MACD_BOTTOM

# 策略共振判定参数
# 兼容旧引用名：真源是 SIGNAL_MACD_BOTTOM（引擎产出的无空格名）
MACD_DIVERGENCE_NAME = SIGNAL_MACD_BOTTOM
RSRS_CONFLUENCE_ZSCORE = 0.7
CONFLUENCE_SIGNAL_NAME = "⚡策略共振 (底背离+RSRS)"
MULTI_FACTOR_NAME = "多因子综合走强"

# 优先级判定参数（历史回测胜率）
PRIORITY_MIN_WIN_RATE = 0.8
PRIORITY_MIN_SAMPLES = 3


def _normalize(name: str) -> str:
    """信号名归一化：去掉空格，兼容历史带空格的写法（如 "MACD 底背离"）。"""
    return (name or "").replace(" ", "")


def append_obv_signals(signals: list[dict], obv_signals: list[dict]) -> list[dict]:
    """将 OBV 低位吸筹检测结果转换为标准信号格式并追加。

    去重：引擎 ``scan_all_timeframes`` 已在日线产出 "OBV碎步吸筹"
    （与本函数同源于 ``check_accumulation``）时跳过，避免同一现象推两条
    重复信号（P0 回归）。
    """
    if not obv_signals:
        return signals
    has_daily_obv = any(
        "OBV" in s.get("name", "") and s.get("tf", "").lower() == "daily"
        for s in signals
    )
    if has_daily_obv:
        return signals
    for sig in obv_signals:
        signals.append(
            {
                "name": f"OBV 低位累积 ({sig['level']})",
                "tf": "Daily",
                "time": sig["time"],
            }
        )
    return signals


def is_confluence(signals: list[dict], rsrs_z: float) -> bool:
    """底背离 + RSRS 走强（zscore > 0.7）构成策略共振。

    比对前对信号名做空格归一化：引擎产出 "MACD底背离"（无空格），历史测试
    注入 "MACD 底背离"（有空格），两者都必须命中（P0 修复：旧实现精确比对
    带空格名，导致生产环境共振从未触发）。
    """
    target = _normalize(MACD_DIVERGENCE_NAME)
    has_macd_div = any(_normalize(s.get("name", "")) == target for s in signals)
    return has_macd_div and rsrs_z > RSRS_CONFLUENCE_ZSCORE


def is_priority_symbol(daily_stats: dict | None) -> tuple[bool, str]:
    """高历史胜率（>=80% 且样本 >=3）判定为优先关注标的。

    Returns:
        (is_priority, 胜率展示标签)
    """
    if daily_stats and daily_stats.get("total_signals", 0) >= 3:
        if daily_stats["win_rate"] >= 0.8:
            return True, f" [💎 历史胜率 {daily_stats['win_rate'] * 100:.0f}%]"
    return False, ""


def apply_confluence(signals: list[dict], score: int) -> tuple[list[dict], int]:
    """追加策略共振信号并将评分抬升至至少 4。"""
    signals.append(
        {
            "name": CONFLUENCE_SIGNAL_NAME,
            "tf": "Daily",
            "time": time.strftime("%H:%M"),
        }
    )
    return signals, max(score, 4)


def append_multi_factor_fallback(
    signals: list[dict], score: int, threshold: int, wr_label: str
) -> list[dict]:
    """无信号但评分达到门槛时，追加多因子综合走强信号。"""
    if not signals and score >= threshold:
        signals.append(
            {
                "name": MULTI_FACTOR_NAME + wr_label,
                "tf": "Daily",
                "time": time.strftime("%H:%M"),
            }
        )
    return signals
