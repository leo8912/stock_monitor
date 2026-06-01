import os
import sys

import pandas as pd
import yfinance as yf

sys.path.append(r"d:\code\stock")
from stock_monitor.core.engine.wave_analyzer import WaveAnalyzer

# 5月29日 收盘数据
realtime_data = {
    "000559.SZ": {
        "name": "万向钱潮",
        "open": 15.49,
        "high": 15.55,
        "low": 14.65,
        "close": 14.78,
    },
    "600879.SS": {
        "name": "航天电子",
        "open": 20.89,
        "high": 20.96,
        "low": 19.18,
        "close": 19.51,
    },
    "605296.SS": {
        "name": "神农集团",
        "open": 26.49,
        "high": 27.55,
        "low": 26.12,
        "close": 27.12,
    },
    "688110.SS": {
        "name": "东芯股份",
        "open": 148.96,
        "high": 149.60,
        "low": 138.04,
        "close": 142.16,
    },
    "600452.SS": {
        "name": "涪陵电力",
        "open": 13.17,
        "high": 13.91,
        "low": 13.00,
        "close": 13.79,
    },
    "002384.SZ": {
        "name": "东山精密",
        "open": 222.93,
        "high": 229.95,
        "low": 210.70,
        "close": 213.05,
    },
}


def analyze_all():
    os.environ["NO_PROXY"] = "*"
    for code, info in realtime_data.items():
        print(f"\n{'='*60}")
        print(f"分析股票: {info['name']} ({code}) - 5月29日 收盘分析")

        # 获取日线历史数据
        df = yf.download(code, start="2024-01-01")
        if df.empty:
            print("下载失败")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()
        # 打印列名以便调试
        print("Columns after reset_index:", df.columns.tolist())
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

        # 确保 datetime 存在并转换为 datetime 类型
        if "datetime" not in df.columns:
            # 寻找第一列或时间列
            # 可能是首列
            df.rename(columns={df.columns[0]: "datetime"}, inplace=True)
        df["datetime"] = pd.to_datetime(df["datetime"])

        # 排除掉今天可能已经存在的行（以防 yfinance 已经拉到了今天的部分数据）
        today_str = "2026-05-28"
        df = df[df["datetime"].dt.strftime("%Y-%m-%d") != today_str]

        # 追加今日的 11:30 假定日线Bar
        new_row = {
            "datetime": pd.to_datetime(today_str),
            "open": info["open"],
            "high": info["high"],
            "low": info["low"],
            "close": info["close"],
            "volume": 0,
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # 进行波浪分析
        result = WaveAnalyzer.analyze(df)
        if not result:
            print("分析失败，数据不足")
            continue

        print(
            f"当前价格: {info['close']} | 昨收: {df.iloc[-2]['close']:.2f} | 涨幅: {(info['close'] - df.iloc[-2]['close'])/df.iloc[-2]['close']*100:+.2f}%"
        )
        print(f"当前浪型判断: {result.current_wave['wave']}")
        print(f"趋势: {result.current_wave['trend']}")
        print(f"描述: {result.current_wave['desc']}")
        print(f"置信度: {result.current_wave['confidence']:.2f}")

        print("\n最近极值点:")
        for s in result.swings[-6:]:
            print(f"  {s.date_str[:10]}: {s.type} 价格={s.price:.2f}")

        print("\n斐波那契支撑阻力位 (基于最近波段):")
        for k, v in sorted(result.fib_levels.items(), key=lambda x: x[1]):
            # 标记最临近的阻力或支撑
            dist = info["close"] - v
            marker = " <- 当前价上方(阻力)" if dist < 0 else " <- 当前价下方(支撑)"
            if abs(dist) < 0.1:
                marker += " [临近临界点!]"
            print(f"  {k:8s}: {v:6.2f} {marker}")


if __name__ == "__main__":
    analyze_all()
