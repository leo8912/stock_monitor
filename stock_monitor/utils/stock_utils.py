"""
股票工具模块
提供统一的股票代码处理功能
"""


class StockCodeProcessor:
    """股票代码处理器"""

    @staticmethod
    def format_stock_code(code: str) -> str | None:
        """
        格式化股票代码，确保正确的前缀

        Args:
            code: 股票代码字符串

        Returns:
            格式化后的股票代码，如果无效则返回None
        """
        if not isinstance(code, str) or not code:
            return None

        if " " in code:
            parts = code.split()
            if not parts:
                return None
            # "code name" 取第一段；"sh 600519" 这类前缀+空格会被截断成
            # 仅前缀导致校验失败，此时回退为去掉空白的整体
            result = StockCodeProcessor._validate_code(parts[0])
            if result is None and len(parts) > 1:
                result = StockCodeProcessor._validate_code("".join(parts))
            return result
        return StockCodeProcessor._validate_code(code)

    @staticmethod
    def _validate_code(code: str) -> str | None:
        """对单个候选代码做规范化与校验（format_stock_code 的内部实现）。"""
        code = code.strip().lower()

        # 移除可能存在的额外字符
        code = "".join(c for c in code if c.isalnum())

        if not code:
            return None

        # 检查是否已经有正确前缀
        if code.startswith(("sh", "sz")):
            # 验证代码长度和数字部分
            if len(code) == 8 and code[2:].isdigit():
                return code
            else:
                return None

        # 港股代码处理
        elif code.startswith("hk"):
            # 验证代码长度和数字部分
            if len(code) == 7 and code[2:].isdigit():
                return code
            else:
                return None

        # 6位纯数字代码（应该避免这种情况，但在某些情况下可能需要处理）
        elif len(code) == 6 and code.isdigit():
            # 特殊处理容易混淆的代码
            if code == "000001":
                # 000001 不再默认处理，需要明确前缀
                # 由调用方决定是上证指数还是平安银行
                return code
            elif code.startswith("6") or code.startswith("5"):
                return "sh" + code
            elif code.startswith(("0", "3", "2")):
                return "sz" + code
            else:
                return "sz" + code  # 默认当作深圳股票

        # 其他情况返回原始代码
        return code

    @classmethod
    def clean_code(cls, stock_code: str) -> str:
        """
        清理股票代码,移除特殊字符并格式化

        Args:
            stock_code: 原始股票代码

        Returns:
            清理后的股票代码
        """
        # 移除emoji等特殊字符
        cleaned = stock_code.replace("⭐️", "").strip()

        # 如果为空,返回原始值
        if not cleaned:
            return stock_code

        # 尝试提取第一部分(处理 "code name" 格式)
        parts = cleaned.split()
        if not parts:
            return stock_code

        # 先尝试格式化第一部分
        formatted = cls.format_stock_code(parts[0])
        if formatted:
            return formatted

        # 如果第一部分格式化失败,尝试整个字符串
        formatted = cls.format_stock_code(cleaned)
        return formatted if formatted else stock_code
