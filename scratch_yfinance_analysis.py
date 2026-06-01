import os
import sys

import pandas as pd
import yfinance as yf

sys.path.append(r"d:\code\stock")
from stock_monitor.core.engine.wave_analyzer import WaveAnalyzer


def analyze_stock(name, code):
    print(f"\n{'='*60}")
    print(f"获取 {name}({code}) 的日线数据(yfinance)...")

    df = yf.download(code, start="2023-10-01")

    if df.empty:
        print(f"无数据: {code}")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df.rename(
        columns={
            "Date": "datetime",
            "Open": "open",
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Volume": "volume",
        },
        inplace=True,
    )

    print(f"数据获取完成，共 {len(df)} 条记录。")
    print("----- 波浪分析 -----")
    result = WaveAnalyzer.analyze(df)
    if not result:
        print("波浪分析失败或数据不足")
    else:
        print(f"当前浪型判断: {result.current_wave['wave']}")
        print(f"趋势: {result.current_wave['trend']}")
        print(f"描述: {result.current_wave['desc']}")
        print(f"置信度: {result.current_wave['confidence']}")
        print("\n最近极值点:")
        for s in result.swings[-6:]:
            print(f"  {s.date_str}: {s.type} 价格={s.price}")

        print("\n斐波那契位:")
        for k, v in result.fib_levels.items():
            print(f"  {k}: {v:.2f}")

        swings = [s for s in result.swings if s.type != "current"]

        print("\n----- 时间与空间结构 -----")

        analyze_swings = swings[-5:] if len(swings) >= 5 else swings

        for i in range(1, len(analyze_swings)):
            p_start = analyze_swings[i - 1]
            p_end = analyze_swings[i]

            p_start_price = float(p_start.price)
            p_end_price = float(p_end.price)

            space_diff = p_end_price - p_start_price
            space_pct = (space_diff / p_start_price) * 100
            direction = "上涨" if space_diff > 0 else "下跌"

            start_idx = p_start.index
            end_idx = p_end.index
            time_diff = end_idx - start_idx

            print(
                f"波段 {i}: {str(p_start.date_str)[:10]} 至 {str(p_end.date_str)[:10]} ({direction})"
            )
            print(
                f"  > 空间: {p_start_price:.2f} -> {p_end_price:.2f} | 跌幅/涨幅: {space_pct:+.2f}%"
            )
            print(f"  > 时间: {time_diff} 个交易日")


def main():
    stocks = [{"name": "涪陵电力", "code": "600452.SS"}]
    os.environ["NO_PROXY"] = "*"
    for s in stocks:
        analyze_stock(s["name"], s["code"])


if __name__ == "__main__":
    main()
