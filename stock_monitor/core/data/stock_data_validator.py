"""
股票数据验证模块
负责验证股票数据的完整性和正确性
"""

import math
from typing import Any


class StockDataValidator:
    """股票数据验证类"""

    @staticmethod
    def is_valid(stock_data: dict[str, Any]) -> bool:
        """
        检查股票数据基础有效性（仅核心价格字段 now/close 存在且为有限数值）。

        如需完整性校验（含 name/open/high/low/volume），请使用
        :meth:`validate_required_fields`。

        Args:
            stock_data: 股票数据字典

        Returns:
            bool: 数据基础有效性
        """
        if not isinstance(stock_data, dict):
            return False

        # 检查关键字段是否存在且不为None
        required_fields = ["now", "close"]
        for field in required_fields:
            if field not in stock_data or stock_data[field] is None:
                return False

        # 检查关键字段是否为有限数值（拒绝 NaN/Inf，避免静默污染下游计算）
        try:
            now = float(stock_data["now"])
            close = float(stock_data["close"])
            return math.isfinite(now) and math.isfinite(close)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def handle_special_cases(
        info: dict[str, Any], pure_code: str, code: str, should_copy: bool = True
    ) -> dict[str, Any] | None:
        """
        处理特殊情况下的股票数据名称安全网。
        quotes() 现已通过腾讯接口正确获取指数数据，此处仅兜底修正名称。

        默认（should_copy=True）在需要修正名称时复制输入字典，避免原地修改
        调用方数据；确安全时可传 should_copy=False 省去拷贝开销。
        """
        if pure_code == "000001":
            if code == "sh000001":
                if info.get("name") != "上证指数":
                    info = info.copy() if should_copy else info
                    info["name"] = "上证指数"
            elif code == "sz000001":
                if info.get("name") != "平安银行":
                    info = info.copy() if should_copy else info
                    info["name"] = "平安银行"
        return info

    @staticmethod
    def get_stock_info(data: dict[str, Any], code: str) -> dict[str, Any] | None:
        """
        获取股票信息并进行验证

        Args:
            data (Dict[str, Any]): 股票数据字典
            code (str): 股票代码

        Returns:
            Optional[Dict[str, Any]]: 股票信息或None
        """
        info = None
        # 优先使用完整代码作为键进行精确匹配,防止 sh000001 和 000001 混淆
        if isinstance(data, dict):
            info = data.get(code)  # 精确匹配完整代码

        # 如果没有精确匹配,尝试使用纯数字代码匹配
        if info is None and isinstance(data, dict):
            pure_code = code[2:] if code.startswith(("sh", "sz")) else code
            info = data.get(pure_code)

        # 兜底修正名称（copy=True 避免污染原始 data dict）
        if info is not None:
            pure_code = code[2:] if code.startswith(("sh", "sz")) else code
            info = StockDataValidator.handle_special_cases(
                info, pure_code, code, should_copy=True
            )

        return info

    @staticmethod
    def validate_required_fields(stock_data: dict[str, Any]) -> bool:
        """
        验证股票数据是否包含所有必需字段

        Args:
            stock_data: 股票数据字典

        Returns:
            bool: 是否包含所有必需字段
        """
        required_fields = ["name", "now", "close", "open", "high", "low", "volume"]
        return all(
            field in stock_data and stock_data[field] is not None
            for field in required_fields
        )
