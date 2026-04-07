"""兼容旧路径: 从 core.resolvers 重新导出符号解析器。"""

from stock_monitor.core.resolvers.symbol_resolver import (
    SymbolConfig,
    SymbolResolver,
    SymbolType,
)

__all__ = ["SymbolConfig", "SymbolResolver", "SymbolType"]
