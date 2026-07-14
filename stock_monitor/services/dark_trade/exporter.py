"""暗盘统计 Excel 导出"""

from __future__ import annotations

from pathlib import Path

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.utils.logger import app_logger


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
