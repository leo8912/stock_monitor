from enum import Enum


class SymbolType(Enum):
    STOCK = "stock"
    INDEX = "index"
    ETF = "etf"
    OTHER = "other"


class SymbolConfig:
    def __init__(
        self,
        code: str,
        market: int,
        symbol_type: SymbolType,
        alternates: list[tuple[str, int]] = None,
    ):
        self.code = code
        self.market = market
        self.type = symbol_type
        self.alternates = alternates or []


class SymbolResolver:
    """
    [ELEGANT] A-股符号标准化解析器
    负责处理前端符号、内部API代码、影子代码映射与标的类型识别
    """

    # 特殊标的映射表 (解决 TDX 服务端代码冲突)
    _SPECIAL_CODES = {
        "sh000001": SymbolConfig(
            "999999", 1, SymbolType.INDEX, alternates=[("000001", 1)]
        ),
        "sz399001": SymbolConfig("399001", 0, SymbolType.INDEX),
        "sz399006": SymbolConfig("399006", 0, SymbolType.INDEX),
    }

    @classmethod
    def resolve(cls, symbol: str, market: int = None) -> SymbolConfig:
        """
        将任意格式的符号解析为标准配置
        """
        s_lower = symbol.lower()

        # 1. 优先检查预定义的特殊映射
        if s_lower in cls._SPECIAL_CODES:
            return cls._SPECIAL_CODES[s_lower]

        # 2. 处理带前缀的标准符号 (sh/sz)
        if s_lower.startswith(("sh", "sz")):
            mk = 1 if s_lower.startswith("sh") else 0
            code = symbol[2:]

            # 识别指数特征 (通常 000, 399 开头且不是 6xx/0xx/3xx 股票)
            # 这是一个简单的启发式方法，如果有更完整的数据可以更精确
            stype = SymbolType.STOCK
            if code.startswith(("399", "h00", "0009")) or (
                mk == 1 and code.startswith("000")
            ):
                stype = SymbolType.INDEX

            return SymbolConfig(code, mk, stype)

        # 3. 处理纯代码兼容性 (Fallback)
        if market is not None:
            # 对纯代码的上证指数进行防御性转换
            if symbol == "000001" and market == 1:
                return cls._SPECIAL_CODES["sh000001"]
            return SymbolConfig(symbol, market, SymbolType.STOCK)

        # 4. 默认推断
        mk = 1 if symbol.startswith("6") else 0
        return SymbolConfig(symbol, mk, SymbolType.STOCK)

    @classmethod
    def get_market_prefix(cls, market: int) -> str:
        return "sh" if market == 1 else "sz"
