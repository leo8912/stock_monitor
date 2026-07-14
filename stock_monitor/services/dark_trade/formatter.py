"""暗盘统计消息格式化"""

from __future__ import annotations

from datetime import datetime


def format_dark_trade_stats_message(stats: dict) -> str:
    """格式化暗盘统计推送消息

    Args:
        stats: calculate_dark_trade_stats() 返回的统计结果

    Returns:
        格式化后的消息字符串
    """
    market = stats.get("market_summary", {})
    watchlist = stats.get("watchlist_details", [])
    date_str = stats.get("date", datetime.now().strftime("%Y%m%d"))

    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
        date_display = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
    except Exception:
        date_display = date_str

    total_inflow_yi = market.get("total_inflow_wan", 0) / 10000
    lines = [
        f"📊 暗盘资金统计 ({date_display})",
        "",
        "【全市场概览】",
        f"• 近3日净流入股票数：{market.get('inflow_3day_count', 0)} 只",
        f"• 近5日流入天数>3天：{market.get('inflow_5day_gt3_count', 0)} 只",
        f"• 合计净流入金额：{total_inflow_yi:.2f} 亿元",
    ]

    if watchlist:
        lines.append("")
        lines.append("【自选股暗盘明细】")
        lines.append("代码    名称    3日净流入(万)  5日流入天数  合计流入(万)")
        for item in watchlist:
            code = item["code"]
            name = item["name"][:6] + ".." if len(item["name"]) > 6 else item["name"]
            inflow_3day = item["inflow_3day_wan"]
            inflow_5day = item["inflow_5day_count"]
            total_inflow = item["total_inflow_wan"]
            sign_3day = "+" if inflow_3day >= 0 else ""
            sign_total = "+" if total_inflow >= 0 else ""
            lines.append(
                f"{code}  {name:<8}  {sign_3day}{inflow_3day:.2f}      "
                f"{inflow_5day}天        {sign_total}{total_inflow:.2f}"
            )
    else:
        lines.append("")
        lines.append("【自选股暗盘明细】")
        lines.append("（无自选股）")

    return "\n".join(lines)
