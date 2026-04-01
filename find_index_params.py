from mootdx.quotes import Quotes


def find_sh_index():
    client = Quotes.factory(market="std")

    print("Testing 000001 in different markets:")
    for m in [0, 1]:
        try:
            df = client.bars(symbol="000001", market=m, category=9, offset=1)
            if df is not None and not df.empty:
                print(f"Market {m}, Code 000001: Close={df.iloc[-1]['close']}")
            else:
                print(f"Market {m}, Code 000001: Empty")
        except Exception as e:
            print(f"Market {m}, Code 000001: Error {e}")

    print("\nTesting 999999 in different markets:")
    for m in [0, 1]:
        try:
            df = client.bars(symbol="999999", market=m, category=9, offset=1)
            if df is not None and not df.empty:
                print(f"Market {m}, Code 999999: Close={df.iloc[-1]['close']}")
            else:
                print(f"Market {m}, Code 999999: Empty")
        except Exception as e:
            print(f"Market {m}, Code 999999: Error {e}")

    print("\nTesting 'sh000001' in quotes (for comparison):")
    df_q = client.quotes(symbol=["sh000001", "sz000001"])
    print(df_q[["code", "price", "market"]])


if __name__ == "__main__":
    find_sh_index()
