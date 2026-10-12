"""暗盘模块共享工具函数"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# A股以北京时间（UTC+8）为准，不依赖部署机本地时区
_CN_TZ = timezone(timedelta(hours=8))


def clean_code(code: str) -> str:
    """清理股票代码，去除市场前缀（仅当剩余部分为纯数字时才剥离）

    Args:
        code: 原始股票代码（如 'sh600519', 'sz000559', '600519', 'hk00700'）

    Returns:
        去前缀后的代码（如 '600519', '000559', '00700'）；
        异常输入（空串、'shh600519' 等）原样返回，避免产出错误的半截代码
    """
    if not isinstance(code, str) or not code:
        return code if isinstance(code, str) else ""
    for prefix in ("sh", "sz", "hk", "SH", "SZ", "HK"):
        if code.startswith(prefix):
            rest = code[len(prefix) :]
            return rest if rest.isdigit() else code
    return code


def get_recent_trade_dates(n: int = 5) -> list[str]:
    """获取最近N个交易日日期列表（跳过周末及 ``_HOLIDAYS`` 配置的休市日）

    注意：与 ``market_manager.is_market_open`` 共用同一份节假日数据源
    （当前为空集，行为与仅判周末一致）；需要精确日历时在该处填入日期。

    Args:
        n: 需要获取的交易日数量

    Returns:
        日期列表，格式为 'YYYYMMDD'，最新的在前
    """
    from stock_monitor.core.market.market_manager import _HOLIDAYS

    dates: list[str] = []
    current = datetime.now(_CN_TZ)
    while len(dates) < n:
        if current.weekday() < 5 and current.strftime("%Y-%m-%d") not in _HOLIDAYS:
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates
