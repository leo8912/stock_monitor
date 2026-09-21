"""
量化扫描单标的信号决策纯函数。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 的
``_scan_single_symbol`` 抽离的无状态决策规则：OBV 信号格式化、
策略共振判定、优先级判定与多因子兜底信号。
"""

from __future__ import annotations

import time

# 策略共振判定参数
MACD_DIVERGENCE_NAME = "MACD 底背离"
RSRS_CONFLUENCE_ZSCORE = 0.7
CONFLUENCE_SIGNAL_NAME = "⚡策略共振 (底背离+RSRS)"
MULTI_FACTOR_NAME = "多因子综合走强"

# 优先级判定参数（历史回测胜率）
PRIORITY_MIN_WIN_RATE = 0.8
PRIORITY_MIN_SAMPLES = 3


def append_obv_signals(signals: list[dict], obv_signals: list[dict]) -> list[dict]:
    """将 OBV 低位吸筹检测结果转换为标准信号格式并追加。"""
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
    """底背离 + RSRS 走强（zscore > 0.7）构成策略共振。"""
    has_macd_div = any(s["name"] == MACD_DIVERGENCE_NAME for s in signals)
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

