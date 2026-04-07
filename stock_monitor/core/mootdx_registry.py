"""兼容旧路径: 从 core.resolvers 重新导出 MootdxRegistry。"""

from stock_monitor.core.resolvers.mootdx_registry import MootdxRegistry

__all__ = ["MootdxRegistry"]
