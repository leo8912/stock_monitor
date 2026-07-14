"""暗盘资金统计计算"""

from __future__ import annotations

from datetime import datetime

from stock_monitor.services.dark_trade.service import (
    build_net_flow_index,
    fetch_all_dark_trade,
)
from stock_monitor.services.dark_trade.utils import clean_code, get_recent_trade_dates
from stock_monitor.utils.logger import app_logger


def calculate_dark_trade_stats(
    watchlist_codes: list[str],
    history_days: int = 5,
) -> dict:
    """
    计算暗盘统计数据

    Args:
        watchlist_codes: 自选股代码列表（原始格式，如 'sh600519' / '000559'）
        history_days: 历史天数（默认5天）

    Returns:
        dict with market_summary and watchlist_details
    """
    app_logger.info("[DarkTradeStats] 开始计算暗盘统计数据...")

    recent_dates = get_recent_trade_dates(history_days)
    if not recent_dates:
        app_logger.warning("[DarkTradeStats] 无法获取交易日期")
        return {"market_summary": {}, "watchlist_details": []}

    # 抓取历史数据
    history_data: dict[str, dict[str, float]] = {}
    for d in recent_dates:
        try:
            records = fetch_all_dark_trade(d)
            history_data[d] = build_net_flow_index(records)
            app_logger.info(f"[DarkTradeStats] {d} 暗盘记录: {len(history_data[d])} 只")
        except Exception as e:
            app_logger.warning(f"[DarkTradeStats] {d} 抓取失败: {e}")
            history_data[d] = {}

    # 获取股票名称（使用清理后的code作为key）
    stock_names: dict[str, str] = {}
    try:
        from stock_monitor.data.stock.stock_db import StockDatabase

        db = StockDatabase()
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code, name FROM stocks")
            for row in cursor.fetchall():
                # 同时存储原始code和清理后的code
                raw_code = row[0]
                name = row[1]
                stock_names[raw_code] = name
                # 存储清理后的code（去除市场前缀）
                stock_names[clean_code(raw_code)] = name
    except Exception as e:
        app_logger.warning(f"[DarkTradeStats] 获取股票名称失败: {e}")

    # 统计全市场数据
    all_codes: set[str] = set()
    for d_data in history_data.values():
        all_codes.update(d_data.keys())

    inflow_3day_count = 0
    inflow_5day_gt3_count = 0
    total_inflow_wan = 0.0

    for code in all_codes:
        daily_nets = [history_data.get(d, {}).get(code, 0.0) for d in recent_dates]
        inflow_3day = sum(daily_nets[:3])
        if inflow_3day > 0:
            inflow_3day_count += 1
        inflow_5day_count = sum(1 for v in daily_nets if v > 0)
        if inflow_5day_count > 3:
            inflow_5day_gt3_count += 1
        total_inflow_wan += sum(daily_nets)

    market_summary = {
        "inflow_3day_count": inflow_3day_count,
        "inflow_5day_gt3_count": inflow_5day_gt3_count,
        "total_inflow_wan": total_inflow_wan,
    }

    # 统计自选股数据
    watchlist_clean = {clean_code(c) for c in watchlist_codes}
    watchlist_details = []

    for code in watchlist_clean:
        daily_nets = [history_data.get(d, {}).get(code, 0.0) for d in recent_dates]
        watchlist_details.append(
            {
                "code": code,
                "name": stock_names.get(code, code),
                "inflow_3day_wan": sum(daily_nets[:3]),
                "inflow_5day_count": sum(1 for v in daily_nets if v > 0),
                "total_inflow_wan": sum(daily_nets),
            }
        )

    watchlist_details.sort(key=lambda x: x["inflow_3day_wan"], reverse=True)

    return {
        "market_summary": market_summary,
        "watchlist_details": watchlist_details,
        "date": recent_dates[0] if recent_dates else datetime.now().strftime("%Y%m%d"),
    }
