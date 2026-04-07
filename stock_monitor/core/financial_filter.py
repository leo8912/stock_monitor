"""兼容旧路径: 从 core.engine 重新导出 FinancialFilter。"""

from stock_monitor.core.engine.financial_filter import FinancialFilter

__all__ = ["FinancialFilter"]
