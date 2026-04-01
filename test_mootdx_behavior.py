from mootdx.quotes import Quotes


def test_mootdx_symbols():
    client = Quotes.factory(market="std")

    # 1. Test quotes with prefixes
    symbols = ["sh000001", "sz000001", "sz000559"]
    df_quotes = client.quotes(symbol=symbols)
    print("--- Quotes with Prefixes ---")
    print(df_quotes[["code", "price"]] if df_quotes is not None else "Failed")

    # 2. Test bars with prefixes (mootdx .bars usually takes code and market separately)
    # Let's see if it works with symbol
    try:
        df_bars = client.bars(symbol="sh000001", category=9, offset=5)
        print("\n--- Bars with Prefix (sh000001) ---")
        print(df_bars.tail(2))
    except Exception as e:
        print(f"\nBars with prefix failed: {e}")

    # 3. Test bars with numeric code and market index (the standard way)
    df_bars_std = client.bars(symbol="000001", market=1, category=9, offset=5)
    print("\n--- Bars with (000001, market=1) ---")
    print(df_bars_std.tail(2))


if __name__ == "__main__":
    test_mootdx_symbols()
