from mootdx.quotes import Quotes


def get_mootdx_info(code, name):
    print(f"--- {name} ({code}) ---")
    client = Quotes.factory(market="std")
    market = 1 if code.startswith("6") else 0
    try:
        # Quote
        q = client.quotes(market=market, symbol=code)
        if not q.empty:
            row = q.iloc[0]
            print(
                f"Mootdx: Price={row.get('price')}, LastClose={row.get('last_close')}"
            )

        # Daily
        k_d = client.kdata(market=market, symbol=code, frequency=9).tail(20)
        if not k_d.empty:
            print(
                f"Daily: Close={k_d['close'].iloc[-1]}, MA5={k_d['close'].rolling(5).mean().iloc[-1]:.2f}"
            )

        # Weekly
        k_w = client.kdata(market=market, symbol=code, frequency=5).tail(20)
        if not k_w.empty:
            print(
                f"Weekly: Close={k_w['close'].iloc[-1]}, MA5={k_w['close'].rolling(5).mean().iloc[-1]:.2f}"
            )
    except Exception as e:
        print(f"Error mootdx: {e}")
    print("\n")


stocks = [
    {"code": "000559", "name": "万向钱潮"},
    {"code": "002600", "name": "领益智造"},
    {"code": "002407", "name": "多氟多"},
    {"code": "600460", "name": "士兰微"},
]

for s in stocks:
    get_mootdx_info(s["code"], s["name"])
