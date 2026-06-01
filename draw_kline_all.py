import os

import mplfinance as mpf
import pandas as pd
import yfinance as yf

stocks = [
    {
        "name": "航天电子",
        "code": "600879.SS",
        "high": 27.35,
        "low": 20.43,
        "fib": [25.87, 24.71, 23.89, 23.07, 22.06],
    },
    {
        "name": "神农集团",
        "code": "605296.SS",
        "high": 31.57,
        "low": 27.10,
        "fib": [30.61, 29.86, 29.34, 28.81, 28.15],
    },
    {
        "name": "中欣氟材",
        "code": "002915.SZ",
        "high": 24.50,
        "low": 19.88,
        "fib": [23.51, 22.74, 22.19, 21.64, 20.97],
    },
    {
        "name": "东芯股份",
        "code": "688110.SS",
        "high": 166.60,
        "low": 147.30,
        "fib": [162.47, 159.23, 156.95, 154.67, 151.85],
    },
    {
        "name": "万向钱潮",
        "code": "000559.SZ",
        "high": 18.60,
        "low": 15.57,
        "fib": [17.95, 17.44, 17.09, 16.73, 16.29],
    },
]

out_dir = r"C:\Users\leo89\.gemini\antigravity-ide\brain\b834177c-eb63-4be2-97da-5bb29fbac8d9\scratch"
os.makedirs(out_dir, exist_ok=True)

for s in stocks:
    code = s["code"]
    df = yf.download(code, start="2023-10-01")
    if df.empty:
        continue
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    df_plot = df.tail(80)

    out_file = os.path.join(out_dir, f"chart_{code[:6]}.png")

    hlines_vals = [
        s["high"],
        s["fib"][0],
        s["fib"][1],
        s["fib"][2],
        s["fib"][3],
        s["fib"][4],
        s["low"],
    ]
    colors = ["red", "orange", "orange", "yellow", "green", "green", "blue"]
    hlines = {
        "hlines": hlines_vals,
        "colors": colors,
        "linestyle": "--",
        "linewidths": 1,
    }

    mpf.plot(
        df_plot,
        type="candle",
        style="yahoo",
        title=f"{s['name']} ({code[:6]}) K-Line & Fibonacci",
        hlines=hlines,
        volume=True,
        savefig={"fname": out_file, "dpi": 120, "bbox_inches": "tight"},
    )
    print(f"Saved {s['name']}")
