"""
股票数据验证模块
负责验证股票数据的完整性和正确性
"""

from typing import Any, Optional

# from ..utils.helpers import is_equal  # Unused import removed


class StockDataValidator:
    """股票数据验证类"""

    @staticmethod
    def is_valid(stock_data: dict[str, Any]) -> bool:
        """
        检查股票数据是否完整有效

        Args:
            stock_data: 股票数据字典

        Returns:
            bool: 数据是否有效
        """
        if not isinstance(stock_data, dict):
            return False

        # 检查关键字段是否存在且不为None
        required_fields = ["now", "close"]
        for field in required_fields:
            if field not in stock_data or stock_data[field] is None:
                return False

        # 检查关键字段是否为有效数值
        try:
            float(stock_data["now"])
            float(stock_data["close"])
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def handle_special_cases(
        info: dict[str, Any], pure_code: str, code: str, should_copy: bool = False
    ) -> Optional[dict[str, Any]]:
        """
        处理特殊情况下的股票数据(如上证指数和平安银行)

        Args:
            info (Dict[str, Any]): 股票信息
            pure_code (str): 纯股票代码
            code (str): 完整股票代码
            should_copy (bool): 是否需要复制数据以避免修改原始数据

        Returns:
            Optional[Dict[str, Any]]: 处理后的股票信息
        """
        if pure_code == "000001":
            # 检查是否应该显示为上证指数
            if code == "sh000001":
                # 强制修正名称为上证指数
                info = info.copy() if should_copy else info  # 创建副本避免修改原始数据
                info["name"] = "上证指数"
            elif code == "sz000001":
                # 强制修正名称为平安银行
                info = info.copy() if should_copy else info  # 创建副本避免修改原始数据
                info["name"] = "平安银行"
        return info

    @staticmethod
    def get_stock_info(data: dict[str, Any], code: str) -> Optional[dict[str, Any]]:
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
        if not info and isinstance(data, dict):
            # 提取纯数字代码
            pure_code = code[2:] if code.startswith(("sh", "sz")) else code
            info = data.get(pure_code)

            # 特殊处理:确保上证指数和平安银行正确映射
            info = StockDataValidator.handle_special_cases(info, pure_code, code)

        # 特殊处理:确保上证指数和平安银行正确映射(即使精确匹配也需处理)
        if info and isinstance(data, dict):
            # 提取纯数字代码
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
        return all(field in stock_data for field in required_fields)


# 创建全局实例(虽然是静态方法,但保持一致性)
stock_data_validator = StockDataValidator()
