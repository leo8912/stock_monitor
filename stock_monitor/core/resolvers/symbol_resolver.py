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
    [ELEGANT] A股符号标准化解析器。
    负责处理前端符号、内部 API 代码、影子代码映射与标的类型识别。
    """

    _SPECIAL_CODES = {
        "999999": SymbolConfig(
            "999999", 1, SymbolType.INDEX, alternates=[("000001", 1)]
        ),
        "sh000001": SymbolConfig(
            "999999", 1, SymbolType.INDEX, alternates=[("000001", 1)]
        ),
        "sz399001": SymbolConfig("399001", 0, SymbolType.INDEX),
        "sz399006": SymbolConfig("399006", 0, SymbolType.INDEX),
    }

    @classmethod
    def resolve(cls, symbol: str, market: int = None) -> SymbolConfig:
        """
        将任意格式的符号解析为标准配置。
        """
        s_lower = symbol.lower()

        if s_lower in cls._SPECIAL_CODES:
            return cls._SPECIAL_CODES[s_lower]

        if s_lower.startswith(("sh", "sz")):
            mk = 1 if s_lower.startswith("sh") else 0
            code = symbol[2:]

            stype = SymbolType.STOCK
            if code.startswith(("399", "h00", "0009")) or (
                mk == 1 and code.startswith("000")
            ):
                stype = SymbolType.INDEX

            return SymbolConfig(code, mk, stype)

        if market is not None:
            if symbol == "000001" and market == 1:
                return cls._SPECIAL_CODES["sh000001"]
            if symbol == "999999" and market == 1:
                return cls._SPECIAL_CODES["999999"]
            return SymbolConfig(symbol, market, SymbolType.STOCK)

        if symbol == "999999":
            return cls._SPECIAL_CODES["999999"]

        mk = 1 if symbol.startswith("6") else 0
        return SymbolConfig(symbol, mk, SymbolType.STOCK)

    @classmethod
    def get_market_prefix(cls, market: int) -> str:
        return "sh" if market == 1 else "sz"
