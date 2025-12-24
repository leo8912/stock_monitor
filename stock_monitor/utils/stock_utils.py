"""
股票工具模块
提供统一的股票代码处理功能
"""

from typing import Any, Optional


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
                # 即使格式不完全正确，也返回原始代码
                return code

        # 港股代码处理
        elif code.startswith("hk"):
            # 验证代码长度和数字部分
            if len(code) == 7 and code[2:].isdigit():
                return code
            else:
                # 即使格式不完全正确，也返回原始代码
                return code

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


def extract_stocks_from_list(items: list[Any]) -> list[str]:
    """
    从列表项中提取股票代码列表

    Args:
        items: 列表项对象列表

    Returns:
        股票代码列表
    """
    processor = StockCodeProcessor()
    stocks = []

    for item in items:
        if item is not None:
            # 检查对象是否有text方法（如QListWidgetItem）
            if hasattr(item, "text") and callable(item.text):
                text = item.text().strip()
            else:
                text = str(item).strip()

            code, _ = processor.extract_code_from_text(text)

            # 确保代码有效后再添加
            if code:
                formatted_code = processor.format_stock_code(code)
                if formatted_code:
                    stocks.append(formatted_code)
            # 如果没有分离出code但text本身就是一个有效的股票代码，则直接使用text
            elif text:
                formatted_code = processor.format_stock_code(text)
                if formatted_code:
                    stocks.append(formatted_code)

    # 去除重复项，保持原有顺序
    seen = set()
    unique_stocks = []
    for stock in stocks:
        if stock not in seen:
            seen.add(stock)
            unique_stocks.append(stock)

    return unique_stocks
