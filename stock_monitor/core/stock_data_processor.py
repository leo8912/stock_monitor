"""
数据处理核心模块
负责统一处理股票数据的清洗、转换和计算
"""

import math
from typing import Any, Optional

from stock_monitor.utils.logger import app_logger

# 涨跌颜色常量 —— 值与 ui.constants.COLORS 保持同步
# 不直接 import ui.constants，避免 core → ui 循环依赖
_STOCK_COLORS = {
    "UP_LIMIT": "#FF0000",  # 涨停
    "UP_BRIGHT": "#FF4500",  # 大涨
    "UP": "#e74c3f",  # 上涨
    "NEUTRAL": "#e6eaf3",  # 平盘
    "DOWN": "#27ae60",  # 下跌
    "DOWN_DEEP": "#1e8449",  # 大跌
    "DOWN_LIMIT": "#145a32",  # 跌停
}


class StockDataProcessor:
    """股票数据处理器"""

    @staticmethod
    def process_raw_data(code: str, raw_data: dict[str, Any]) -> tuple:
        """
        处理原始股票数据，返回UI展示所需的元组格式

        Args:
            code: 股票代码
            raw_data: 原始数据字典

        Returns:
            Tuple: (name, price, change_str, color, seal_vol, seal_type)
        """
        # 1. 处理特殊股票名称（如上证指数）
        info = StockDataProcessor._handle_special_stocks(code, raw_data)

        # 2. 提取名称
        name = StockDataProcessor._extract_name(code, info)

        # 3. 提取价格数据
        price_info = StockDataProcessor._extract_price_info(code, info)

        if not price_info:
            return (name, "--", "--", "#e6eaf3", "", "")

        price, change_str, color, now_price, close_price = price_info

        # 4. 计算封单信息
        seal_vol, seal_type = StockDataProcessor._calculate_seal_info(info, now_price)

        return (name, price, change_str, color, seal_vol, seal_type)

    @staticmethod
    def _handle_special_stocks(code: str, info: dict[str, Any]) -> dict[str, Any]:
        """处理特殊股票代码的名称映射"""
        pure_code = code[2:] if code.startswith(("sh", "sz")) else code

        if pure_code == "000001":
            if code == "sh000001":
                # 只有当原名不是预期时才修改，或者强制修改
                # 这里为了简单直接返回副本
                info = info.copy()
                info["name"] = "上证指数"
            elif code == "sz000001":
                info = info.copy()
                info["name"] = "平安银行"
        return info

    @staticmethod
    def _extract_name(code: str, info: dict[str, Any]) -> str:
        """提取并格式化股票名称"""
        name = info.get("name", code)
        # 港股处理：去除英文部分
        if code.startswith("hk") and "-" in name:
            name = name.split("-")[0].strip()
        return name

    @staticmethod
    def _extract_price_info(code: str, info: dict[str, Any]) -> Optional[tuple]:
        """
        提取价格信息
        Returns:
            (price_str, change_str, color_str, float_now, float_close)
        """
        try:
            now = info.get("now") or info.get("price")
            close = info.get("close") or info.get("lastPrice") or now

            # 价格有效性检查与回退逻辑
            is_now_valid = False
            if now is not None:
                try:
                    if float(now) > 0:
                        is_now_valid = True
                except (ValueError, TypeError):
                    pass

            if not is_now_valid and close is not None:
                try:
                    if float(close) > 0:
                        # Debug log removed to avoid spam, or kept at debug level
                        now = close
                except (ValueError, TypeError):
                    pass

            # 最终验证
            if now is None or close is None:
                return None

            f_now = float(now)
            f_close = float(close)

            # 计算涨跌幅
            percent = ((f_now - f_close) / f_close * 100) if f_close != 0 else 0

            # 颜色逻辑 - 使用统一的颜色常量
            if percent >= 10:
                color = _STOCK_COLORS["UP_LIMIT"]  # 涨停-最亮红
            elif percent >= 5:
                color = _STOCK_COLORS["UP_BRIGHT"]  # 大涨-亮红
            elif percent > 0:
                color = _STOCK_COLORS["UP"]  # 上涨-标准红
            elif percent == 0:
                color = _STOCK_COLORS["NEUTRAL"]  # 平盘-灰白
            elif percent > -5:
                color = _STOCK_COLORS["DOWN"]  # 下跌-标准绿
            elif percent > -10:
                color = _STOCK_COLORS["DOWN_DEEP"]  # 大跌-深绿
            else:
                color = _STOCK_COLORS["DOWN_LIMIT"]  # 跌停-最深绿

            return (f"{f_now:.2f}", f"{percent:+.2f}%", color, f_now, f_close)

        except (ValueError, TypeError, Exception) as e:
            app_logger.warning(f"处理股票 {code} 价格信息失败: {e}")
            return None

    @staticmethod
    def _calculate_seal_info(info: dict[str, Any], now_price: float) -> tuple[str, str]:
        """计算封单信息"""
        try:
            high = float(info.get("high", 0))
            low = float(info.get("low", 0))
            bid1 = float(info.get("bid1", 0))
            ask1 = float(info.get("ask1", 0))
            bid1_vol = float(info.get("bid1_volume", 0) or info.get("volume_2", 0))
            ask1_vol = float(info.get("ask1_volume", 0) or info.get("volume_3", 0))

            # 涨停判断
            # 简单判断：价格等于最高价，且等于买一价，且买一量>0，卖一为0
            if (
                math.isclose(now_price, high, rel_tol=1e-5)
                and math.isclose(now_price, bid1, rel_tol=1e-5)
                and bid1_vol > 0
                and ask1 <= 1e-6
            ):  # ask1 <= 1e-6 used to safely evaluate 0.0 or 0 for floats
                # 注意：原始逻辑中校验的是 str(ask1) == "0.0"
                # 这里使用更稳健的比较

                vol = int(bid1_vol)
                display_vol = f"{int(vol/100000)}k" if vol >= 100000 else str(vol)
                return (display_vol, "up")

            # 跌停判断
            if (
                math.isclose(now_price, low, rel_tol=1e-5)
                and math.isclose(now_price, ask1, rel_tol=1e-5)
                and ask1_vol > 0
                and bid1 <= 1e-6
            ):
                vol = int(ask1_vol)
                display_vol = f"{int(vol/100000)}k" if vol >= 100000 else str(vol)
                return (display_vol, "down")

        except Exception as e:
            app_logger.debug(f"计算股票封单信息失败: {e}")
        return ("", "")


# 全局实例
stock_processor = StockDataProcessor()
