import json
import os
import sys

# 确保能导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_monitor.core.backtest_engine import BacktestEngine
from stock_monitor.core.container import container
from stock_monitor.core.quant_engine import QuantEngine
from stock_monitor.core.stock_data_fetcher import StockDataFetcher


def run_rsrs():
    fetcher = container.get(StockDataFetcher)
    engine = QuantEngine(fetcher.mootdx_client)
    backtester = BacktestEngine(engine)

    stocks = [
        ("万向钱潮", "000559"),
        ("领益智造", "002600"),
        ("多氟多", "002407"),
        ("士兰微", "600460"),
    ]

    results = {}
    print(
        f"{'股票名称':<10} | {'周期':<8} | {'信号数':<6} | {'胜率':<8} | {'平均收益':<10}"
    )
    print("-" * 60)

    for name, code in stocks:
        market = 1 if code.startswith("6") else 0

        # 1. Daily RSRS
        stats_d = backtester.get_rsrs_strategy_stats(code, market, category=9)
        if stats_d:
            print(
                f"{name:<10} | {'日线':<8} | {stats_d['total_signals']:<8} | {stats_d['win_rate']*100:>6.1f}% | {stats_d['avg_profit']*100:>8.2f}%"
            )
            results[f"{code}_daily"] = stats_d

        # 2. 60m RSRS
        stats_60 = backtester.get_rsrs_strategy_stats(code, market, category=3)
        if stats_60:
            print(
                f"{name:<10} | {'60分钟':<8} | {stats_60['total_signals']:<8} | {stats_60['win_rate']*100:>6.1f}% | {stats_60['avg_profit']*100:>8.2f}%"
            )
            results[f"{code}_60m"] = stats_60

    # 保存结果
    with open(
        "analysis_reports/rsrs_backtest_results.json", "w", encoding="utf-8"
    ) as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nRSRS Backtest Results Saved.")


if __name__ == "__main__":
    run_rsrs()
