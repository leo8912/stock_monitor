from mootdx.quotes import Quotes


def list_api_methods():
    client = Quotes.factory(market="std")
    if client is None:
        print("Init failed")
        return

    print("API methods for mootdx StdQuotes:")
    methods = [m for m in dir(client) if not m.startswith("_")]
    print(", ".join(methods))

    # 查找含有 auction, pre, call 之类的名字
    keywords = ["auction", "pre", "call", "bid", "ask"]
    found = [m for m in methods if any(kw in m.lower() for kw in keywords)]
    print("\nKeywords hint methods:")
    print(found)


if __name__ == "__main__":
    list_api_methods()
