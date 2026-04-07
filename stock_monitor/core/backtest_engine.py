"""兼容旧路径: 从 core.engine 重新导出 BacktestEngine。"""

from stock_monitor.core.engine.backtest_engine import BacktestEngine

__all__ = ["BacktestEngine"]
