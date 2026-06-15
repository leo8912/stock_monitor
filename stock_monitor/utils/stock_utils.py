"""
股票工具模块
提供统一的股票代码处理功能
"""

from typing import Optional


class StockCodeProcessor:
    """股票代码处理器"""

    @staticmethod
    def format_stock_code(code: str) -> Optional[str]:
        """
        格式化股票代码，确保正确的前缀

        Args:
            code: 股票代码字符串

        Returns:
            格式化后的股票代码，如果无效则返回None
        """
        if not isinstance(code, str) or not code:
            return None

        # 如果代码包含空格，只取第一部分
        if " " in code:
            code = code.split()[0]

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

    @staticmethod
    def extract_code_from_text(text: str) -> tuple[Optional[str], str]:
        """
        从文本中提取股票代码

        Args:
            text: 包含股票代码的文本

        Returns:
            (提取到的代码, 处理后的文本)
        """
        if not isinstance(text, str):
            return None, ""

        text = text.strip()
        if not text:
            return None, ""

        # 移除emoji
        if text.startswith(("🇭🇰", "⭐️", "📈", "📊", "🏦", "🛡️", "⛽️", "🚗", "💻")):
            text = text[2:].strip()

        code = None
        # 特殊处理港股，直接提取代码
        if text.startswith("hk"):
            # 港股代码格式为hkxxxxx
            parts = text.split()
            if len(parts) >= 1:
                code = parts[0]  # 港股代码就是第一部分
        else:
            # 从搜索结果格式 "code name" 中提取代码
            parts = text.split()
            if len(parts) >= 2:
                # 如果是搜索结果格式，第一部分是代码
                code = parts[0]
            elif len(parts) == 1:
                # 如果只有一个部分，假设它是代码
                code = parts[0]

        # 确保提取到的代码符合股票代码格式
        if code and not code.startswith(("sh", "sz", "hk")):
            # 如果代码不以sh、sz或hk开头，则认为提取失败
            code = None

        return code, text
