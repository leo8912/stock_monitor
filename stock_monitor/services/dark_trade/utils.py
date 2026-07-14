"""暗盘模块共享工具函数"""

from __future__ import annotations

from datetime import datetime, timedelta


def clean_code(code: str) -> str:
    """清理股票代码，去除市场前缀，统一6位

    Args:
        code: 原始股票代码（如 'sh600519', 'sz000559', '600519'）

    Returns:
        清理后的6位代码（如 '600519', '000559'）
    """
    for prefix in ("sh", "sz", "hk", "SH", "SZ", "HK"):
        if code.startswith(prefix):
            return code[len(prefix) :]
    return code


def get_recent_trade_dates(n: int = 5) -> list[str]:
    """获取最近N个交易日日期列表（简单跳过周末）

    Args:
        n: 需要获取的交易日数量

    Returns:
        日期列表，格式为 'YYYYMMDD'，最新的在前
    """
    dates: list[str] = []
    current = datetime.now()
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates
