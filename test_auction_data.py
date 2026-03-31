import time

from mootdx.quotes import Quotes


def test_auction_data():
    client = Quotes.factory(market="std")
    stocks = [
        {"code": "600000", "market": 1},
        {"code": "000001", "market": 0},
        {"code": "300059", "market": 0},
        {"code": "510050", "market": 1},
    ]

    output_file = "d:/code/stock/auction_test_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"集合竞价行情测试 (当前时刻: {time.strftime('%Y-%m-%d %H:%M:%S')})\n")
        f.write("=" * 50 + "\n")

        for s in stocks:
            code = s["code"]
            market = s["market"]
            f.write(f"\n--- {code} 交易数据 ---\n")

            try:
                df = client.transaction(symbol=code, market=market, start=0, count=200)
                if df is not None and not df.empty:
                    f.write(f"条数: {len(df)}\n")
                    f.write(f"时间段: {df['time'].min()} - {df['time'].max()}\n")
                    f.write("最新 20 条:\n" + df.head(20).to_string() + "\n")

                    auction = df[df["time"] <= "09:25:00"]
                    if not auction.empty:
                        f.write(
                            f"竞价数据 ({len(auction)} 条):\n"
                            + auction.to_string()
                            + "\n"
                        )
                    else:
                        f.write("未见竞价数据\n")
                else:
                    f.write(f"无获取到 {code} 数据\n")
            except Exception as e:
                f.write(f"错误: {e}\n")

        f.write("\n" + "-" * 50 + "\n快照行情:\n")
        try:
            codes = ["sh600000", "sz000001", "sz300059"]
            q_df = client.quotes(symbol=codes)
            if q_df is not None and not q_df.empty:
                f.write(q_df.to_string() + "\n")
        except Exception as e:
            f.write(f"获取快照错误: {e}\n")

    print(f"测试完成，结果已保存至: {output_file}")


if __name__ == "__main__":
    test_auction_data()
