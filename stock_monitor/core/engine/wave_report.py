"""
波浪分析报告文本格式化模块。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 抽离的
无状态波浪分析文案构建函数。只依赖 ``WaveAnalyzer`` 的分析结果，
不涉及 Qt 线程、推送或状态管理，便于独立测试与复用。
"""

from __future__ import annotations

from .wave_analyzer import WaveAnalyzer


def get_prev_next_wave(wave: str) -> tuple[str, str]:
    """获取前一浪和预计下一浪"""
    progression = ["1", "2", "3", "4", "5", "A", "B", "C"]
    if wave not in progression:
        return "未知", "未知"
    idx = progression.index(wave)
    prev_w = progression[(idx - 1) % len(progression)]
    next_w = progression[(idx + 1) % len(progression)]
    return prev_w, next_w


def analyze_major_and_sub_waves(df):
    """先按粗阈值寻找大浪结构，再以细阈值分析子浪，返回 (大浪, 子浪)。"""
    major_res = None
    for t in [0.08, 0.06, 0.05]:
        major_res = WaveAnalyzer.analyze(df, threshold=t)
        if major_res:
            break
    sub_res = WaveAnalyzer.analyze(df, threshold=0.03)
    return major_res, sub_res


def resolve_sub_wave(sub_res) -> tuple[str, str]:
    """从子浪分析结果解析浪型标识与说明，无结果时返回空串。"""
    if sub_res and sub_res.current_wave:
        return (
            sub_res.current_wave.get("wave", "未知"),
            sub_res.current_wave.get("desc", ""),
        )
    return "", ""


def build_fib_support_resistance(levels: dict, curr_price: float) -> tuple[str, str]:
    """根据斐波那契位与当前价拆分支撑位与阻力位字符串。"""
    supports, resistances = [], []
    sorted_levels = sorted(
        [(k, v) for k, v in levels.items() if k not in ("start", "end")],
        key=lambda x: x[1],
    )
    for k, v in sorted_levels:
        if v < curr_price:
            supports.append(f"{v:.2f}")
        elif v > curr_price:
            resistances.append(f"{v:.2f}")

    support_str = " / ".join(supports[-3:]) if supports else "无"
    resistance_str = " / ".join(resistances[:3]) if resistances else "无"
    return support_str, resistance_str


def format_wave_history_lines(all_waves: list[dict]) -> list[str]:
    """格式化历史波段（时间 + 空间）文本行，含当前位置标记。"""
    lines = ["", "近期走势:"]
    for wd in all_waves:
        duration = f"{wd['duration_days']}天" if wd["duration_days"] > 0 else "?"
        sign = "+" if wd["pct_change"] >= 0 else ""
        arrow = "↓" if wd["direction"] == "down" else "↑"
        marker = " ←当前位置" if wd["is_current"] else ""
        lines.append(
            f"  {arrow} {wd['label']}: "
            f"{wd['from_date'][5:]}->{wd['to_date'][5:]} "
            f"({duration}) {sign}{wd['pct_change']:.1f}%{marker}"
        )
    return lines


def format_remaining_space_lines(rs: dict) -> list[str]:
    """格式化剩余空间预估（目标位 / 空间 / 预计天数）文本行。"""
    sign = "+" if rs["remaining_pct"] >= 0 else ""
    return [
        "",
        "剩余空间预估:",
        f"  目标位: {rs['target_price']:.2f} ({rs['basis']})",
        f"  当前->目标: {sign}{rs['remaining_pct']:.1f}%",
        f"  预计完成: 约{rs['remaining_days_est']}个交易日",
    ]


def explain_wave(wave: str, trend: str | None) -> str:
    """用通俗语言解释当前浪型含义"""
    explanations = {
        ("1", "bullish"): "筑底完成，刚刚启动上涨",
        ("2", "bullish"): "上涨后回踩确认，正常调整",
        ("3", "bullish"): "主升浪，涨幅最大、速度最快的阶段",
        ("4", "bullish"): "上涨途中休整，蓄力后有望再冲高",
        ("5", "bullish"): "上涨末期，动能衰减，追高风险大",
        ("A", "bearish"): "上涨结束，开始下跌调整",
        ("B", "bearish"): "下跌途中的反弹，空间有限",
        ("C", "bearish"): "加速下跌阶段，杀伤力最大",
    }
    return explanations.get((wave, trend), "")


def wave_action_hint(wave: str, trend: str | None) -> str:
    """给出简洁的操作建议"""
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


def format_wave_text_analysis(symbol: str, name: str, timeframe_name: str, df) -> str:
    """将波浪分析结果格式化为简洁易懂的文本卡片"""
    if df is None or df.empty or len(df) < 30:
        return ""

    # 大浪分析 + 子浪分析
    major_res, sub_res = analyze_major_and_sub_waves(df)

    if not major_res or not major_res.current_wave:
        return ""

    mw = major_res.current_wave
    wave = mw.get("wave", "未知")
    trend = mw.get("trend")
    conf = mw.get("confidence", 0.5) * 100
    rule_check = mw.get("rule_check", "")

    sub_wave, sub_desc = resolve_sub_wave(sub_res)

    curr_price = float(major_res.df.iloc[-1]["close"])

    support_str, resistance_str = build_fib_support_resistance(
        major_res.fib_levels or {}, curr_price
    )

    # 趋势判断
    trend_tag = "看涨" if trend == "bullish" else "看跌"

    # ── 构建简洁文案 ──────────────────────────────────────
    lines = [
        f"[波浪分析] {name} ({symbol})  {timeframe_name}",
        f"趋势: {trend_tag} | 当前: 第{wave}浪 | 置信度: {conf:.0f}%",
    ]

    # 浪型通俗说明
    wave_explain = explain_wave(wave, trend)
    if wave_explain:
        lines.append(f"状态: {wave_explain}")

    if sub_wave:
        lines.append(f"细分: 第{sub_wave}浪 ({sub_desc})")

    if rule_check:
        lines.append(f"规则: {rule_check}")

    # 历史波段（时间 + 空间）— 只显示最近几段
    if major_res.all_waves:
        lines.extend(format_wave_history_lines(major_res.all_waves))

    lines.extend(
        [
            "",
            f"价格: {curr_price:.2f}",
            f"支撑: {support_str}",
            f"阻力: {resistance_str}",
        ]
    )

    # 剩余空间预估
    if major_res.remaining_space:
        lines.extend(format_remaining_space_lines(major_res.remaining_space))

    lines.append("")
    lines.append(wave_action_hint(wave, trend))

    return "\n".join(lines)

