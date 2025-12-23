"""
行情数据处理模块
负责用于获取和处理股票行情数据

该模块包含获取行情数据、处理行情数据等功能。
"""

import datetime
from typing import Any, Dict, Optional

import easyquotation

from stock_monitor.utils.logger import app_logger


def get_quotation_engine(market_type: str = "sina") -> Optional[Any]:
    """获取行情引擎实例"""
    try:
        engine: Any = easyquotation.use(market_type)
        app_logger.debug(f"行情引擎初始化成功: {market_type}")
        return engine
    except Exception as e:
        error_msg = f"初始化行情引擎失败: {e}"
        app_logger.error(error_msg)
        return None


def is_market_open() -> bool:
    """检查A股是否开市"""
    # 复用config/manager.py中的实现

    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return (datetime.time(9, 30) <= t <= datetime.time(11, 30)) or (
        datetime.time(13, 0) <= t <= datetime.time(15, 0)
    )


def get_name_by_code(code: str) -> str:
    """股票代码获取股票名称"""
    # 从SQLite数据库获取股票名称
    try:
        from stock_monitor.data.stock.stock_db import stock_db

        stock_info = stock_db.get_stock_by_code(code)
        if stock_info:
            name = stock_info["name"]
            # 对于港股，只保留中文部分
            if code.startswith("hk"):
                # 去除"-"及之后的部分，只保留中文名称
                if "-" in name:
                    name = name.split("-")[0].strip()
            return name
    except Exception as e:
        app_logger.warning(f"从SQLite数据库获取股票 {code} 名称失败: {e}")
    return ""


def get_stock_info_by_code(code: str) -> Optional[Dict[str, str]]:
    """根据股票代码获取股票完整信息"""
    # 从SQLite数据库获取股票信息
    try:
        from stock_monitor.data.stock.stock_db import stock_db

        stock_info = stock_db.get_stock_by_code(code)
        if stock_info:
            # 对于港股，只保留中文部分
            if code.startswith("hk") and "-" in stock_info["name"]:
                stock_info["name"] = stock_info["name"].split("-")[0].strip()
            return stock_info
    except Exception as e:
        app_logger.warning(f"从SQLite数据库获取股票 {code} 信息失败: {e}")
    return None
