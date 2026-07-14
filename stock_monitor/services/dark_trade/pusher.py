"""暗盘统计推送到企业微信"""

from __future__ import annotations

from stock_monitor.services.dark_trade.calculator import calculate_dark_trade_stats
from stock_monitor.services.dark_trade.formatter import format_dark_trade_stats_message
from stock_monitor.utils.logger import app_logger


def push_dark_trade_stats(config: dict, watchlist_codes: list[str]) -> bool:
    """推送暗盘统计到企业微信

    Args:
        config: 配置字典（包含企微推送配置）
        watchlist_codes: 自选股代码列表

    Returns:
        是否推送成功
    """
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

        return success
    except Exception as e:
        app_logger.error(f"[DarkTradeStats] 推送异常: {e}")
        return False
