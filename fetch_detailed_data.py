import os
import time
from datetime import datetime

import akshare as ak

# Disable proxy to avoid connection issues
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""


def get_detailed_stock_analysis(code, name):
    print(f"--- {name} ({code}) ---")

    # 1. Real-time Spot
    for retry in range(3):
        try:
            spot = ak.stock_zh_a_spot_em()
            row = spot[spot["代码"] == code].iloc[0]
            print(
                f"Spot: Price={row['最新价']}, Pct={row['涨跌幅']}%, Turnover={row['换手率']}%, PE={row['市盈率-动态']}"
            )
            break
        except Exception as e:
            if retry == 2:
                print(f"Error spot: {e}")
            time.sleep(1)

    # 2. Daily, Weekly, Monthly Analysis
    for period in ["daily", "weekly", "monthly"]:
        for retry in range(3):
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=code, period=period, adjust="qfq"
                ).tail(20)
                if hist.empty:
                    print(f"{period.capitalize()}: No data")
                    break
                last_close = hist["收盘"].iloc[-1]
                prev_close = hist["收盘"].iloc[0]
                change = (last_close - prev_close) / prev_close * 100
                ma5 = hist["收盘"].rolling(5).mean().iloc[-1]
                ma10 = hist["收盘"].rolling(10).mean().iloc[-1]
                print(
                    f"{period.capitalize()}: Close={last_close}, PeriodChange={change:.2f}%, MA5={ma5:.2f}, MA10={ma10:.2f}"
                )
                break
            except Exception as e:
                if retry == 2:
                    print(f"Error {period}: {e}")
                time.sleep(1)

    # 3. Capital Flow (Argument is 'stock')
    for retry in range(3):
        try:
            flow = ak.stock_individual_fund_flow(
                stock=code,
                market="sz" if code.startswith(("000", "002", "300")) else "sh",
            )
            if not flow.empty:
                latest = flow.iloc[0]
                print(f"MainFlow: {latest.get('主力净流入-净额', 'N/A')} 万元")
                break
            else:
                print("MainFlow: No data")
                break
        except Exception as e:
            if retry == 2:
                print(f"Error flow: {e}")
            time.sleep(1)

    # 4. Financial Abstract
    for retry in range(3):
        try:
            fin = ak.stock_financial_abstract(symbol=code)
            if not fin.empty:
                latest = fin.iloc[0]
                print(
                    f"Financial: ROE={latest.get('净资产收益率', 'N/A')}, NetProfit={latest.get('净利润', 'N/A')}"
                )
                break
            else:
                print("Financial: No data")
                break
        except Exception as e:
            if retry == 2:
                print(f"Error financial: {e}")
            time.sleep(1)
    print("\n")


stocks = [
    {"code": "000559", "name": "万向钱潮"},
    {"code": "002600", "name": "领益智造"},
    {"code": "002407", "name": "多氟多"},
    {"code": "600460", "name": "士兰微"},
]

print(f"Analysis Time: {datetime.now()}")
for s in stocks:
    get_detailed_stock_analysis(s["code"], s["name"])
