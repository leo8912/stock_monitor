import os
import sys

for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if k in os.environ:
        del os.environ[k]
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
import akshare as ak
import pandas as pd

sys.path.append(r"d:\code\stock")

from stock_monitor.core.engine.wave_analyzer import WaveAnalyzer


def main():
    print("获取万向钱潮(000559)的日线数据...")
    # 获取一年半左右的数据
    df = ak.stock_zh_a_hist(
        symbol="000559", period="daily", start_date="20240101", adjust="qfq"
    )

    df.rename(
        columns={
            "日期": "datetime",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        },
        inplace=True,
    )

    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    print(
        f"数据获取完成，共 {len(df)} 条记录。最新日期: {df.iloc[-1]['datetime']} 收盘价: {df.iloc[-1]['close']}"
    )
    print("开始波浪分析...")

    result = WaveAnalyzer.analyze(df)
    if not result:
        print("波浪分析失败或数据不足")
        return

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


if __name__ == "__main__":
    main()
