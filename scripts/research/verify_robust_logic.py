from mootdx.quotes import Quotes


# 模拟 QuantEngine 的核心解析与抓取逻辑
def test_robust_fetch():
    client = Quotes.factory(market="std")

    symbol = "sh000001"
    # 模拟候选逻辑
    candidate_codes = [("999999", 1), ("000001", 1)]

    print(f"开始验证 {symbol} 的稳健获取逻辑...")

    for code, market in candidate_codes:
        try:
            print(f"尝试代码: {code}, 市场: {market}")
            df = client.bars(symbol=code, market=market, category=9, offset=1)

            if df is not None and not df.empty:
                price = df.iloc[-1]["close"]
                print(f"获取到价格: {price}")

                # 范围校验
                if price < 100:
                    print(f"⚠️ 价格 {price} 过低，判定为非指数数据，跳过。")
                    continue

                print(f"✅ 成功! 获取到正确的指数点位: {price}")
                return
            else:
                print("空数据，尝试下一个。")
        except Exception as e:
            print(f"❌ 解析异常: {e}，尝试下一个。")


if __name__ == "__main__":
    test_robust_fetch()
