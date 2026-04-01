from mootdx.quotes import Quotes


def verify_flow(symbol="601138"):
    print(f"正在建立通达信行情连接，核对 {symbol} 原始逐笔数据...")

    # 1. 初始化行情客户端
    client = Quotes.factory(market="std")

    # 2. 获取逐笔成交 (最近 2000 笔)
    # 工业富联在主板，market=1 (SH)
    df = client.transaction(symbol=symbol, market=1, start=0, count=2000)

    if df is None or df.empty:
        print("无法获取成交数据，请检查网络或股票代码。")
        return

    # 3. 计算金额并过滤大单 (50万阈值)
    df["amount"] = df["price"] * df["vol"] * 100
    big_orders = df[df["amount"] >= 500000].copy()

    print(f"\n找到最近 {len(big_orders)} 笔大单 (>= 50万):")
    print("-" * 60)
    print(f"{'时间':<10} {'价格':<8} {'成交额':<12} {'方向':<10} {'逻辑判定'}")
    print("-" * 60)

    buy_sum = 0
    sell_sum = 0

    for _, row in big_orders.iterrows():
        # 0: 买入 (主动买/外盘), 1: 卖出 (主动卖/内盘), 2: 中性
        direction = (
            "买入"
            if row["buyorsell"] == 0
            else "卖出"
            if row["buyorsell"] == 1
            else "中性"
        )
        is_inflow = (
            "流入 (+)"
            if row["buyorsell"] == 0
            else "流出 (-)"
            if row["buyorsell"] == 1
            else "忽略"
        )

        if row["buyorsell"] == 0:
            buy_sum += row["amount"]
        if row["buyorsell"] == 1:
            sell_sum += row["amount"]

        print(
            f"{row['time']:<10} {row['price']:<8.2f} {row['amount']:<12.0f} {direction:<10} {is_inflow}"
        )

    print("-" * 60)
    print("统计结果:")
    print(f"大单买入总额: {buy_sum:,.0f} 元")
    print(f"大单卖出总额: {sell_sum:,.0f} 元")
    print(f"当前 BATCH 净流向: {buy_sum - sell_sum:,.0f} 元")

    if buy_sum - sell_sum < 0:
        print("\n结论：原始数据确实显示【大单净流出】。")
        print("这意味着在当前的 2000 笔交易中，主力在利用高位砸向买盘（内盘成交多）。")
    else:
        print("\n结论：数据显示【大单净流入】。")


if __name__ == "__main__":
    verify_flow()
