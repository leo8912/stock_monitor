from mootdx.quotes import Quotes


def analyze_call_auction_live():
    client = Quotes.factory(market="std")
    # 抽取平安银行 000001
    symbol = "000001"

    print(f"--- 正在分析 {symbol} 今日集合竞价数据 ---")

    # 1. 直接拉取 transaction
    # TDX 分笔是由 start 指定偏移量，由于 09:25 是第一笔，我们尝试回溯
    df = client.transaction(symbol=symbol, market=0, start=0, count=2000)
    if df is not None and not df.empty:
        # 寻找 09:25:00 之前的记录
        auction_rows = df[df["time"] <= "09:25"]
        if not auction_rows.empty:
            print("\n发现集合竞价数据记录:")
            print(auction_rows.head(5))

            # 第一笔 (通常是 09:25:0x)
            first_trade = auction_rows.iloc[-1]  # 由于是倒序，-1 是最晚的一笔 09:25
            print(f"\n竞价正式成交时刻: {first_trade['time']}")
            print(f"竞价成交价: {first_trade['price']}")
            print(f"竞价成交手: {first_trade['vol']}")

            # 计算竞价成交额 (TDX vol 是手)
            auction_amount = float(first_trade["price"] * first_trade["vol"] * 100)
            print(f"竞价成交额: {auction_amount / 10000:.2f} 万")

        else:
            print("未找到 09:25 之前的集合竞价成交记录，可能已被服务器清空。")

    # 2. 检查 quotes (模拟开盘前)
    q_df = client.quotes(symbol=[symbol])
    if q_df is not None:
        print("\n当前盘口状态 (包含挂单):")
        fields = ["price", "bid1", "bid_vol1", "ask1", "ask_vol1"]
        print(q_df[fields])


if __name__ == "__main__":
    analyze_call_auction_live()
