"""
暗盘统计数据计算与推送模块
收盘后计算全市场和自选股的暗盘资金流向统计，推送到企业微信
"""

from __future__ import annotations

from datetime import datetime, timedelta

from stock_monitor.services.dark_trade_service import (
    build_net_flow_index,
    fetch_all_dark_trade,
)
from stock_monitor.utils.logger import app_logger


def _get_recent_trade_dates(n: int = 5) -> list[str]:
    """获取最近N个交易日日期列表（简单跳过周末）"""
    dates: list[str] = []
    current = datetime.now()
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates  # 最新的在前


def _clean_code(code: str) -> str:
    """清理股票代码，去除市场前缀，统一6位"""
    for prefix in ("sh", "sz", "hk", "SH", "SZ", "HK"):
        if code.startswith(prefix):
            return code[len(prefix) :]
    return code


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

    recent_dates = _get_recent_trade_dates(history_days)
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
                stock_names[_clean_code(raw_code)] = name
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
    watchlist_clean = {_clean_code(c) for c in watchlist_codes}
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


def format_dark_trade_stats_message(stats: dict) -> str:
    """格式化暗盘统计推送消息"""
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
                f"{code}  {name:<8}  {sign_3day}{inflow_3day:.2f}      {inflow_5day}天        {sign_total}{total_inflow:.2f}"
            )
    else:
        lines.append("")
        lines.append("【自选股暗盘明细】")
        lines.append("（无自选股）")

    return "\n".join(lines)


def push_dark_trade_stats(config: dict, watchlist_codes: list[str]) -> bool:
    """推送暗盘统计到企业微信，并导出Excel"""
    try:
        stats = calculate_dark_trade_stats(watchlist_codes)
        if not stats.get("market_summary"):
            app_logger.warning("[DarkTradeStats] 无统计数据，跳过推送")
            return False

        message = format_dark_trade_stats_message(stats)
        from stock_monitor.services.notifier import NotifierService

        title = "📊 暗盘资金统计"
        success = NotifierService.dispatch_custom_message(config, title, message)
        if success:
            app_logger.info("[DarkTradeStats] 暗盘统计推送成功")
        else:
            app_logger.warning("[DarkTradeStats] 暗盘统计推送失败")

        # 同时导出Excel
        try:
            excel_path = export_dark_trade_stats_excel(watchlist_codes)
            if excel_path:
                app_logger.info(f"[DarkTradeStats] Excel已导出: {excel_path}")
        except Exception as e:
            app_logger.warning(f"[DarkTradeStats] Excel导出失败: {e}")

        return success
    except Exception as e:
        app_logger.error(f"[DarkTradeStats] 推送异常: {e}")
        return False


def export_dark_trade_stats_excel(
    watchlist_codes: list[str],
    history_days: int = 5,
    output_dir: str | None = None,
) -> str | None:
    """
    导出暗盘统计到Excel

    筛选条件：3日净流入 > 0 且 5日流入天数 > 3

    Args:
        watchlist_codes: 自选股代码列表
        history_days: 历史天数
        output_dir: 输出目录（默认 analysis_reports）

    Returns:
        导出文件路径，失败返回None
    """
    try:
        from datetime import datetime
        from pathlib import Path

        import pandas as pd

        # 计算统计
        stats = calculate_dark_trade_stats(watchlist_codes, history_days)

        if not stats.get("market_summary"):
            app_logger.warning("[DarkTradeStats] 无统计数据，跳过导出")
            return None

        # 筛选符合条件的股票：3日净流入 > 0 且 5日流入天数 > 3
        watchlist = stats.get("watchlist_details", [])
        filtered = [
            item
            for item in watchlist
            if item["inflow_3day_wan"] > 0 and item["inflow_5day_count"] > 3
        ]

        if not filtered:
            app_logger.info(
                "[DarkTradeStats] 无符合条件的股票（3日净流入>0且5日流入天数>3）"
            )
            return None

        # 创建DataFrame
        df = pd.DataFrame(filtered)
        df = df.rename(
            columns={
                "code": "代码",
                "name": "名称",
                "inflow_3day_wan": "3日净流入(万)",
                "inflow_5day_count": "5日流入天数",
                "total_inflow_wan": "合计流入(万)",
            }
        )

        # 排序：按3日净流入降序
        df = df.sort_values("3日净流入(万)", ascending=False)

        # 确定输出路径
        if output_dir is None:
            output_dir = "analysis_reports"
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        date_str = stats.get("date", datetime.now().strftime("%Y%m%d"))
        filename = f"dark_trade_stats_{date_str}.xlsx"
        output_path = Path(output_dir) / filename

        # 导出Excel
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Sheet 1: 筛选后的股票
            df.to_excel(
                writer, sheet_name="暗盘统计(3日净流入>0且5日>3天)", index=False
            )

            # Sheet 2: 全部自选股
            all_df = pd.DataFrame(watchlist)
            all_df = all_df.rename(
                columns={
                    "code": "代码",
                    "name": "名称",
                    "inflow_3day_wan": "3日净流入(万)",
                    "inflow_5day_count": "5日流入天数",
                    "total_inflow_wan": "合计流入(万)",
                }
            )
            all_df.to_excel(writer, sheet_name="全部自选股", index=False)

            # Sheet 3: 全市场概览
            market_data = stats.get("market_summary", {})
            market_df = pd.DataFrame(
                [
                    {
                        "日期": stats.get("date", ""),
                        "近3日净流入股票数": market_data.get("inflow_3day_count", 0),
                        "近5日流入天数>3天": market_data.get(
                            "inflow_5day_gt3_count", 0
                        ),
                        "合计净流入(万)": market_data.get("total_inflow_wan", 0),
                        "合计净流入(亿)": market_data.get("total_inflow_wan", 0)
                        / 10000,
                    }
                ]
            )
            market_df.to_excel(writer, sheet_name="全市场概览", index=False)

        app_logger.info(f"[DarkTradeStats] Excel导出完成: {output_path}")
        return str(output_path)

    except Exception as e:
        app_logger.error(f"[DarkTradeStats] Excel导出失败: {e}")
        return None


def main() -> None:
    """CLI 入口 - 暗盘资金统计"""
    import argparse

    parser = argparse.ArgumentParser(
        description="暗盘资金统计 - 计算全市场和自选股暗盘净流入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 计算并打印统计（不推送）
  python -m stock_monitor.services.dark_trade_stats --codes sh600519 sz000559

  # 计算并推送到企业微信
  python -m stock_monitor.services.dark_trade_stats --codes sh600519 --push

  # 导出Excel（筛选3日净流入>0且5日流入天数>3）
  python -m stock_monitor.services.dark_trade_stats --codes sh600519 --export

  # 只打印格式化消息
  python -m stock_monitor.services.dark_trade_stats --print-only
        """,
    )
    parser.add_argument(
        "--codes",
        nargs="*",
        default=[],
        help="自选股代码列表（如 sh600519 sz000559）",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="历史天数（默认5天）",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="推送到企业微信",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="导出Excel（筛选3日净流入>0且5日流入天数>3）",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="只打印格式化消息，不推送",
    )
    args = parser.parse_args()

    # 计算统计
    print(f"正在计算暗盘统计数据（{args.days}天历史）...")
    stats = calculate_dark_trade_stats(args.codes, history_days=args.days)

    if not stats.get("market_summary"):
        print("⚠️ 无统计数据（可能非交易时段或网络异常）")
        return

    # 格式化消息
    message = format_dark_trade_stats_message(stats)

    if args.export:
        # 导出Excel模式
        output_path = export_dark_trade_stats_excel(args.codes, history_days=args.days)
        if output_path:
            print(f"✅ Excel导出成功: {output_path}")
        else:
            print("❌ Excel导出失败或无符合条件的数据")
    elif args.push:
        # 推送模式
        from stock_monitor.core.config_center import config_center

        success = push_dark_trade_stats(config_center.snapshot(), args.codes)
        if success:
            print("✅ 推送成功")
        else:
            print("❌ 推送失败")
    else:
        # 打印模式
        print("\n" + message)

    if args.print_only or (not args.push and not args.export):
        print("\n💡 提示:")
        print("  添加 --push 参数可推送到企业微信")
        print("  添加 --export 参数可导出Excel（筛选3日净流入>0且5日流入天数>3）")


if __name__ == "__main__":
    main()
