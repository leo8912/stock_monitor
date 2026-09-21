"""
量化复盘报告文案格式化模块。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 抽离的
无状态报告标题与 Markdown 内容构建函数，便于独立测试与复用。
"""

from __future__ import annotations

from datetime import datetime


def get_report_title(report_type: str, now: datetime | None = None) -> str:
    """获取报告标题"""
    date_str = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")

    titles = {
        "morning": f"📊 早盘复盘 ({date_str})",
        "afternoon": f"📈 午盘复盘 ({date_str})",
        "manual": f"🔍 全量复盘 ({date_str})",
        "auto": f"📉 自动复盘 ({date_str})",
    }

    return titles.get(report_type, titles["auto"])


def format_report_content(
    title: str, all_signals: list, strong_signals: list, report_type: str
) -> str:
    """格式化报告内容（使用 Markdown 格式）"""
    if not all_signals:
        return "今日无显著信号"

    # 按评分排序
    all_signals.sort(key=lambda x: x["score"], reverse=True)
    strong_signals.sort(key=lambda x: x["score"], reverse=True)

    # Markdown 格式报告
    md = [
        f"**{title}**\n\n",
        f"✅ 总信号数：{len(all_signals)} | 🔥 强信号：{len(strong_signals)}\n\n",
    ]

    # 强信号优先展示
    if strong_signals:
        md.append("**🌟 重点关注：**\n")
        for sig in strong_signals[:5]:  # 最多显示 5 个
            fin_label = sig["audit"].get("label", "")
            wave_daily_desc = (
                f" | 🌊日线:{sig['wave_daily']['desc']}"
                if sig.get("wave_daily")
                else ""
            )
            wave_60m_desc = (
                f" | 🌊60m:{sig['wave_60m']['desc']}" if sig.get("wave_60m") else ""
            )
            md.append(
                f"> **{sig['name']}** ({sig['symbol']}) "
                f"[{sig['signals'][0]}] "
                f"评分:{sig['score']:+} "
                f"{fin_label}"
                f"{wave_daily_desc}"
                f"{wave_60m_desc}"
            )
        md.append("")

    # 全部信号列表
    if all_signals:
        md.append("**📋 全部信号：**\n")
        for sig in all_signals[:20]:  # 最多显示 20 个
            price_info = (
                f"￥{sig['price']:.2f} ({sig['pct']:+.1f}%)"
                if sig["price"] > 0
                else "--"
            )
            wave_daily_desc = (
                f" (日线:{sig['wave_daily']['wave']}浪)"
                if sig.get("wave_daily")
                else ""
            )
            wave_60m_desc = (
                f" (60m:{sig['wave_60m']['wave']}浪)" if sig.get("wave_60m") else ""
            )
            md.append(
                f"• {sig['name']} [{sig['signals'][0]}] "
                f"+{sig['score']} "
                f"{price_info}"
                f"{wave_daily_desc}"
                f"{wave_60m_desc}"
            )

    return "\n".join(md)
