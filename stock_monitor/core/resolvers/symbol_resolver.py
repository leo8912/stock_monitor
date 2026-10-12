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
    def _from_special(cls, key: str) -> SymbolConfig:
        # 构造新实例并拷贝 alternates，避免调用方改动污染全局映射表
        cfg = cls._SPECIAL_CODES[key]
        return SymbolConfig(cfg.code, cfg.market, cfg.type, list(cfg.alternates))

    @staticmethod
    def _classify_type(code: str, market: int) -> SymbolType:
        """统一的代码类型识别：399 段（深市指数）与沪市 000 段为指数。

        注意：深市 0009xx 是个股段（如 sz000938），不能按前缀误判为指数。
        """
        if code.startswith("399") or (market == 1 and code.startswith("000")):
            return SymbolType.INDEX
        return SymbolType.STOCK

    @classmethod
    def resolve(cls, symbol: str, market: int = None) -> SymbolConfig:
        """
        将任意格式的符号解析为标准配置。
        """
        if not symbol:
            raise ValueError("symbol 不能为空字符串")

        s_lower = symbol.lower()

        if s_lower in cls._SPECIAL_CODES:
            return cls._from_special(s_lower)

        if s_lower.startswith(("sh", "sz")):
            mk = 1 if s_lower.startswith("sh") else 0
            code = symbol[2:]
            return SymbolConfig(code, mk, cls._classify_type(code, mk))

        if market is not None:
            if symbol == "000001" and market == 1:
                return cls._from_special("sh000001")
            if symbol == "999999" and market == 1:
                return cls._from_special("999999")
            # 显式 market 也走统一类型识别，保证与带前缀路径结论一致
            return SymbolConfig(symbol, market, cls._classify_type(symbol, market))

        if symbol == "999999":
            return cls._from_special("999999")

        # 6 开头沪市主板/科创，5 开头沪市 ETF/基金，其余默认深市
        mk = 1 if symbol.startswith(("6", "5")) else 0
        return SymbolConfig(symbol, mk, SymbolType.STOCK)

    @classmethod
    def get_market_prefix(cls, market: int) -> str:
        return "sh" if market == 1 else "sz"
