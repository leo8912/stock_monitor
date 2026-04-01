from mootdx.quotes import Quotes


def test_bid_ask_columns():
    client = Quotes.factory(market="std")
    # 抽取平安银行
    df = client.quotes(symbol=["000001"])
    if df is not None and not df.empty:
        print("Success! Columns in quotes:")
        print(df.columns.tolist())

        # 打印买卖盘口 (通常是 bid1-bid5, ask1-ask5)
        cols = [
            c
            for c in df.columns
            if "bid" in c or "ask" in c or "buy" in c or "sell" in c
        ]
        if cols:
            print("\nMarket Depth (Bid/Ask) for 000001:")
            # 过滤需要的列并打印第一行
            print(df[cols].iloc[0])
        else:
            print("\nNo Bid/Ask columns found in basic quotes.")
    else:
        print("Failed to get quotes.")


if __name__ == "__main__":
    test_bid_ask_columns()
