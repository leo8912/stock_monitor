"""CLI 入口 - 暗盘资金统计"""

from __future__ import annotations

import argparse

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.services.dark_trade.exporter import export_dark_trade_stats_excel
from stock_monitor.services.dark_trade.formatter import format_dark_trade_stats_message
from stock_monitor.services.dark_trade.pusher import push_dark_trade_stats


def main() -> None:
    """CLI 入口 - 暗盘资金统计"""
    parser = argparse.ArgumentParser(
        description="暗盘资金统计 - 计算全市场和自选股暗盘净流入",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 计算并打印统计（不推送）
  python -m stock_monitor.services.dark_trade.cli --codes sh600519 sz000559

  # 计算并推送到企业微信
  python -m stock_monitor.services.dark_trade.cli --codes sh600519 --push

  # 导出Excel（筛选3日净流入>0且5日流入天数>3）
  python -m stock_monitor.services.dark_trade.cli --codes sh600519 --export

  # 只打印格式化消息
  python -m stock_monitor.services.dark_trade.cli --print-only
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
