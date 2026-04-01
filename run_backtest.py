import json
import os

from mootdx.quotes import Quotes

from stock_monitor.core.backtest_engine import BacktestEngine
from stock_monitor.core.quant_engine import QuantEngine

# Disable proxy
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""


def run_backtest(code_pure, name):
    print(f"--- Backtesting: {name} ({code_pure}) ---")
    client = Quotes.factory(market="std")
    qe = QuantEngine(client)
    be = BacktestEngine(qe)

    market = 1 if code_pure.startswith("6") else 0

    # 1. Backtest MACD Bullish Divergence on different timeframes
    timeframes = {"daily": 9, "60m": 3, "30m": 2, "15m": 1}

    tf_results = {}
    for tf_name, cat in timeframes.items():
        stats = be.get_strategy_stats(code_pure, market, cat)
        if stats:
            tf_results[tf_name] = stats

    # 2. Backtest Score Stats (Score >= 3)
    score_stats = be.get_score_stats(code_pure, market, category=9, min_score=3)

    return {
        "name": name,
        "code": code_pure,
        "strategy_stats": tf_results,
        "score_stats": score_stats,
    }


stocks = [
    {"code": "000559", "name": "万向钱潮"},
    {"code": "002600", "name": "领益智造"},
    {"code": "002407", "name": "多氟多"},
    {"code": "600460", "name": "士兰微"},
]

all_results = []
for s in stocks:
    try:
        res = run_backtest(s["code"], s["name"])
        all_results.append(res)
    except Exception as e:
        print(f"Backtest Error for {s['name']}: {e}")

with open(
    "d:/code/stock/analysis_reports/backtest_results.json", "w", encoding="utf-8"
) as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print("Backtest Data Saved to JSON.")
