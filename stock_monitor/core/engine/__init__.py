"""
量化分析引擎层 (Quant Engine Layer)

职责:
- 技术指标计算 (MACD, RSRS, OBV, RSI, BB, Volume)
- 形态识别和信号生成
- 策略回测和验证
- 金融数据验证

模块包含:
- quant_engine.py: 核心量化引擎
- quant_engine_constants.py: 指标参数和常量
- financial_filter.py: 财务过滤器
- backtest_engine.py: 回测引擎
- wave_analyzer.py: 波浪分析器
- wave_chart.py: 波浪图表

使用方式:
    从子模块按需导入，例如:
        from stock_monitor.core.engine.quant_engine import QuantEngine
        from stock_monitor.core.engine.quant_engine_constants import MACD_WINDOW
"""

from .backtest_engine import BacktestEngine
from .financial_filter import FinancialFilter
from .quant_engine import QuantEngine
from .wave_analyzer import (
    WaveAnalysisResult,
    WaveAnalyzer,
    analyze_and_record,
    explain_wave,
    wave_hint,
)
from .wave_chart import WaveChart

__all__ = [
    "QuantEngine",
    "FinancialFilter",
    "BacktestEngine",
    "WaveAnalyzer",
    "WaveAnalysisResult",
    "WaveChart",
    "explain_wave",
    "wave_hint",
    "analyze_and_record",
]
