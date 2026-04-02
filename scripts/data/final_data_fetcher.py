import os

import akshare as ak

# Disable proxy
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""


def get_data(code):
    try:
        spot = ak.stock_zh_a_spot_em()
        row = spot[spot["代码"] == code].iloc[0]
        # Daily
        hist_d = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(60)
        # Weekly/Monthly
        hist_w = ak.stock_zh_a_hist(symbol=code, period="weekly", adjust="qfq").tail(10)
        hist_m = ak.stock_zh_a_hist(symbol=code, period="monthly", adjust="qfq").tail(
            10
        )
        return {
            "price": row["最新价"],
            "pct": row["涨跌幅"],
            "hist_d": hist_d,
            "hist_w": hist_w,
            "hist_m": hist_m,
        }
    except Exception as e:
        print(f"Error fetching {code}: {e}")
        return None


stocks = ["000559", "002600", "002407", "600460"]
results = {}
for code in stocks:
    data = get_data(code)
    if data:
        results[code] = data

# Print a summary for me to read
for code, res in results.items():
    print(f"[{code}] Price: {res['price']}, Pct: {res['pct']}%")
    print(
        f"Daily: {res['hist_d']['收盘'].iloc[-1]} (MA5: {res['hist_d']['收盘'].rolling(5).mean().iloc[-1]:.2f})"
    )
    print(
        f"Weekly: {res['hist_w']['收盘'].iloc[-1]} ({res['hist_w']['日期'].iloc[-1]})"
    )
    print(
        f"Monthly: {res['hist_m']['收盘'].iloc[-1]} ({res['hist_m']['日期'].iloc[-1]})"
    )
    print("-" * 20)
