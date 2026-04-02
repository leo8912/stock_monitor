import json
import os

from mootdx.quotes import Quotes

from stock_monitor.core.quant_engine import QuantEngine

# Disable proxy
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""


def run_analysis(code_pure, name):
    client = Quotes.factory(market="std")
    engine = QuantEngine(client)

    symbol_full = ("sh" if code_pure.startswith("6") else "sz") + code_pure
    market = 1 if code_pure.startswith("6") else 0

    # 1. Fetch Indicators
    df = engine.fetch_bars(code_pure, market, category=9, offset=800)
    if df is None or df.empty:
        return None

    indicators = engine.calculate_comprehensive_indicators(df)

    # 2. Scan Timeframes for Signals
    signals = engine.scan_all_timeframes(code_pure, market)

    # 3. Intensity Score with Symbol (Audit)
    score, audit = engine.calculate_intensity_score_with_symbol(
        symbol_full, df, signals
    )

    # 4. Large Order Flow
    buy, sell, net = engine.fetch_large_orders_flow(symbol_full)

    # 5. RSRS Indicator
    rsrs_z, rsrs_s = engine.calculate_rsrs(df)

    return {
        "name": name,
        "code": code_pure,
        "indicators": indicators,
        "signals": signals,
        "score": score,
        "audit": audit,
        "money_flow": {"buy": buy, "sell": sell, "net": net},
        "rsrs": {"zcore": rsrs_z, "slope": rsrs_s},
    }


stocks = [
    {"code": "000559", "name": "万向钱潮"},
    {"code": "002600", "name": "领益智造"},
    {"code": "002407", "name": "多氟多"},
    {"code": "600460", "name": "士兰微"},
]

results = []
for s in stocks:
    try:
        res = run_analysis(s["code"], s["name"])
        if res:
            results.append(res)
    except Exception as e:
        print(f"Error analyzing {s['name']}: {e}")

with open(
    "d:/code/stock/analysis_reports/deep_quant_data.json", "w", encoding="utf-8"
) as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Deep Quant Data Saved to JSON.")
