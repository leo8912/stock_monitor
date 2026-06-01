import os
import sys

import mplfinance as mpf
import pandas as pd
import yfinance as yf

sys.path.append(r"d:\code\stock")
from stock_monitor.core.engine.wave_analyzer import WaveAnalyzer

# 11:30 实时数据
realtime_data = {
    "000559.SZ": {
        "name": "万向钱潮",
        "open": 15.62,
        "high": 15.85,
        "low": 15.12,
        "close": 15.33,
    },
    "600879.SS": {
        "name": "航天电子",
        "open": 20.60,
        "high": 21.18,
        "low": 20.30,
        "close": 20.75,
    },
    "605296.SS": {
        "name": "神农集团",
        "open": 27.20,
        "high": 27.29,
        "low": 26.69,
        "close": 26.70,
    },
    "002915.SZ": {
        "name": "中欣氟材",
        "open": 19.83,
        "high": 20.25,
        "low": 19.32,
        "close": 19.58,
    },
    "688110.SS": {
        "name": "东芯股份",
        "open": 146.16,
        "high": 149.50,
        "low": 143.57,
        "close": 149.40,
    },
    "600452.SS": {
        "name": "涪陵电力",
        "open": 13.58,
        "high": 14.08,
        "low": 13.38,
        "close": 13.83,
    },
    "002384.SZ": {
        "name": "东山精密",
        "open": 222.00,
        "high": 223.00,
        "low": 212.40,
        "close": 217.27,
    },
}

out_dir = r"C:\Users\leo89\.gemini\antigravity-ide\brain\b834177c-eb63-4be2-97da-5bb29fbac8d9\scratch"
os.makedirs(out_dir, exist_ok=True)


def generate_charts():
    os.environ["NO_PROXY"] = "*"
    for code, info in realtime_data.items():
        print(f"Generating chart for {info['name']} ({code})...")

        # 1. 下载数据
        df = yf.download(code, start="2024-01-01")
        if df.empty:
            print(f"Failed to download data for {code}")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        if "Date" in df.columns:
            df.rename(columns={"Date": "datetime"}, inplace=True)
        elif "index" in df.columns:
            df.rename(columns={"index": "datetime"}, inplace=True)

        df.rename(
            columns={
                "Open": "open",
                "Close": "close",
                "High": "high",
                "Low": "low",
                "Volume": "volume",
            },
            inplace=True,
        )

        if "datetime" not in df.columns:
            df.rename(columns={df.columns[0]: "datetime"}, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"])

        # 2. 去除可能重复的今日数据，并追加今日的11:30数据
        today_str = "2026-05-28"
        df = df[df["datetime"].dt.strftime("%Y-%m-%d") != today_str]

        new_row = {
            "datetime": pd.to_datetime(today_str),
            "open": info["open"],
            "high": info["high"],
            "low": info["low"],
            "close": info["close"],
            "volume": 0,
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # 3. 运行波浪分析以获取斐波那契线
        result = WaveAnalyzer.analyze(df)
        if not result or not result.fib_levels:
            print(f"Wave analysis failed for {code}")
            continue

        # 4. 准备画图数据
        df.set_index("datetime", inplace=True)
        df.index = pd.to_datetime(df.index)
        df_plot = df.tail(60)  # 最近60天

        # 获取斐波那契支撑阻力位值
        fib = result.fib_levels
        # 我们挑选关键的几条线来画：start, end, 0.236, 0.382, 0.500, 0.618, 0.786
        hlines_vals = []
        colors = []

        keys = ["start", "0.236", "0.382", "0.500", "0.618", "0.786", "end"]
        key_colors = {
            "start": "red",
            "0.236": "orange",
            "0.382": "orange",
            "0.500": "yellow",
            "0.618": "green",
            "0.786": "green",
            "end": "blue",
        }

        for k in keys:
            if k in fib:
                hlines_vals.append(fib[k])
                colors.append(key_colors[k])

        hlines = {
            "hlines": hlines_vals,
            "colors": colors,
            "linestyle": "--",
            "linewidths": 1,
        }

        # 5. 画图并保存
        out_file = os.path.join(out_dir, f"chart_{code[:6]}.png")

        title_str = f"{info['name']} ({code[:6]}) Midday Close: {info['close']:.2f}\nWave: {result.current_wave['wave']} ({result.current_wave['trend']})"

        mpf.plot(
            df_plot,
            type="candle",
            style="yahoo",
            title=title_str,
            hlines=hlines,
            volume=True,
            savefig={"fname": out_file, "dpi": 120, "bbox_inches": "tight"},
        )
        print(f"Saved chart to {out_file}")


if __name__ == "__main__":
    generate_charts()
