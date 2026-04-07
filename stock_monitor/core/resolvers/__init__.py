"""
符号解析层 (Resolver Layer)

职责:
- 股票代码解析 (A股标准化)
- mootdx API注册表管理
- 代码和市场的映射
- 符号规范化

模块包含:
- symbol_resolver.py: 符号解析器
- mootdx_registry.py: mootdx客户端注册
"""

from .mootdx_registry import MootdxNameRegistry
from .symbol_resolver import SymbolResolver, SymbolType

__all__ = ["SymbolResolver", "SymbolType", "MootdxNameRegistry"]
