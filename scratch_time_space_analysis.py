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
    df = ak.stock_zh_a_hist(
        symbol="000559", period="daily", start_date="20231001", adjust="qfq"
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

    df["datetime"] = pd.to_datetime(df["datetime"])

    result = WaveAnalyzer.analyze(df)
    if not result:
        print("波浪分析失败或数据不足")
        return

    swings = [s for s in result.swings if s.type != "current"]
    if len(swings) < 2:
        print("有效波动点不足")
        return

    print("\n" + "=" * 50)
    print("万向钱潮(000559) 时间与空间结构深度分析")
    print("=" * 50)

    # 分析最近的 8 个波段（构成完整的上升五浪+ABC调整）
    analyze_swings = swings[-9:] if len(swings) >= 9 else swings

    print("\n【波段基础数据（时间和空间）】")
    for i in range(1, len(analyze_swings)):
        p_start = analyze_swings[i - 1]
        p_end = analyze_swings[i]

        # 空间计算
        space_diff = p_end.price - p_start.price
        space_pct = (space_diff / p_start.price) * 100
        direction = "上涨" if space_diff > 0 else "下跌"

        # 时间计算
        start_idx = p_start.index
        end_idx = p_end.index
        time_diff = end_idx - start_idx  # 交易日天数

        print(
            f"波段 {i}: {p_start.date_str[:10]} 至 {p_end.date_str[:10]} ({direction})"
        )
        print(
            f"  > 空间: {p_start.price:.2f} -> {p_end.price:.2f} | 绝对变化: {space_diff:+.2f} | 涨跌幅: {space_pct:+.2f}%"
        )
        print(f"  > 时间: {time_diff} 个交易日")

    print("\n【时间与空间比例关系 (斐波那契校验)】")
    # 比较相邻同向或反向波段
    for i in range(2, len(analyze_swings)):
        w1_start = analyze_swings[i - 2]
        w1_end = analyze_swings[i - 1]
        w2_start = analyze_swings[i - 1]
        w2_end = analyze_swings[i]

        w1_space = abs(w1_end.price - w1_start.price)
        w2_space = abs(w2_end.price - w2_start.price)

        w1_time = w1_end.index - w1_start.index
        w2_time = w2_end.index - w2_start.index

        if w1_space > 0:
            space_ratio = w2_space / w1_space
        else:
            space_ratio = 0

        if w1_time > 0:
            time_ratio = w2_time / w1_time
        else:
            time_ratio = 0

        rel_type = (
            "同向(驱动/延伸)"
            if ((w2_end.price - w2_start.price) * (w1_end.price - w1_start.price) > 0)
            else "反向(回调/反弹)"
        )

        print(f"波段 {i} 相比 波段 {i-1} [{rel_type}]:")
        print(
            f"  > 空间比例: {space_ratio:.3f} (常见位: 0.382, 0.5, 0.618, 1.0, 1.618)"
        )
        print(f"  > 时间比例: {time_ratio:.3f} (常见位: 0.618, 1.0, 1.618, 2.0)")


if __name__ == "__main__":
    main()
