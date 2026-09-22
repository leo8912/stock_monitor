"""
量化预警推送文案构建纯函数。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 抽离的
无状态文案构建逻辑（合并推送标题/摘要、展示标签、回测统计与今日轨迹），
由 QuantWorker 传入状态快照，便于独立测试与复用。
"""

from __future__ import annotations

from stock_monitor.utils.logger import app_logger


def format_history_text(history_list: list[dict] | None) -> str:
    """格式化今日轨迹文本（最近 5 条），无历史返回空串。"""
    if not history_list:
        return ""
    return "\n今日轨迹：" + " → ".join(
        [f"{h['time']} {h['name']}" for h in history_list[-5:]]
    )


def build_display_labels(
    stock_name: str, is_priority: bool, is_confluence: bool
) -> tuple[str, str]:
    """构建带优先级/共振标记的展示名称与信号后缀。"""
    display_name = f"🔥 {stock_name}" if is_priority else stock_name
    display_sig = " [精细关注]" if is_priority else ""
    if is_confluence:
        display_name = f"💎【策略共振】{stock_name}"
        display_sig = " [超高可靠/重仓机会]"
    return display_name, display_sig


def format_backtest_stats(stats: dict | None) -> str:
    """将回测统计格式化为推送文案，数据不足返回空串。"""
    if not (stats and stats.get("total_signals", 0) >= 3):
        return ""
    wr = stats["win_rate"] * 100
    ap = stats["avg_profit"] * 100
    icon = "✅" if wr >= 60 else ("⚡" if wr >= 45 else "⚠️")
    return f"\n历史复盘：{icon} 同类评分胜率 {wr:.0f}% (均益 {ap:+.1f}%)"


def merge_signals_text(
    symbol: str, stock_name: str, signals_data: list[dict], history_list: list | None
) -> dict | None:
    """
    将同一股票的多个信号合并为一条精简推送

    Args:
        symbol: 股票代码
        stock_name: 股票名称
        signals_data: 信号列表 [{sig_name, score, audit, p_info, ...}]
        history_list: 今日轨迹历史（快照）

    Returns:
        合并后的推送数据；无信号时返回 None
    """
    if not signals_data:
        return None

    # 取最高分作为主评分
    max_score_sig = max(signals_data, key=lambda x: x["score"])

    # 构建精简标题
    is_confluence = any(s.get("is_confluence") for s in signals_data)
    is_priority = any(s.get("is_priority") for s in signals_data)

    if is_confluence:
        title_prefix = "💎【策略共振】"
    elif is_priority:
        title_prefix = "🔥【精细关注】"
    else:
        title_prefix = "🚨"

    # 价格信息
    p_info = max_score_sig.get("p_info", {})

    # 【优化】检查价格有效性
    if p_info and p_info.get("price", 0) > 0:
        pct = p_info.get("pct", 0.0)
        sign = "+" if pct >= 0 else ""
        price_suffix = f" {sign}{pct:.2f}%"
    else:
        price_suffix = " (价格待更新)"
        app_logger.debug(f"[合并推送] {symbol} 价格数据缺失")

    title = f"{title_prefix}{stock_name} ({symbol}){price_suffix}"

    # 构建信号摘要
    score_summary = ", ".join(
        [f"{s['sig_name']}({s['score']:+})" for s in signals_data]
    )

    # 财务审计（取最优）
    best_audit = max(
        signals_data, key=lambda x: x.get("audit", {}).get("score_offset", 0)
    )
    fin_label = best_audit.get("audit", {}).get("label", "[财务稳健]")
    fin_reasons = " / ".join(best_audit.get("audit", {}).get("reasons", []))
    fin_info = f"{fin_label} {fin_reasons}" if fin_reasons else fin_label

    # 历史轨迹
    history_text = format_history_text(history_list)

    # 构建推送内容（text 通道不渲染 Markdown，不使用 ** 星号）
    cycle_info = (
        f"信号组合：{score_summary}\n\n"
        f"🚀 综合强度：{max_score_sig['score']:+}分\n\n"
        f"🏥 财务审计：{fin_info}"
    )

    if history_text:
        cycle_info += f"\n{history_text}"

    return {
        "title": title,
        "signals_text": f"检测到 {len(signals_data)} 个技术信号",
        "cycle_info": cycle_info,
        "p_info": p_info,
        "max_score": max_score_sig["score"],
    }
