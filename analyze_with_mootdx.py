#!/usr/bin/env python3
"""
使用 mootdx 分析股票 - 万向钱潮、领益智造、士兰微、多氟多
"""

from datetime import datetime

from mootdx.quotes import Quotes


def get_stock_info(stock_code: str, stock_name: str):
    """获取股票基本信息"""
    print(f"\n{'='*60}")
    print(f"📊 {stock_name} ({stock_code})")
    print(f"{'='*60}\n")

    try:
        # 初始化行情引擎
        client = Quotes.factory(market="std")

        # 1. 实时行情（使用_quotes 接口）
        print("【实时行情】")
        try:
            # 获取行情数据
            if stock_code.startswith("6"):
                market = 1  # 上海
            else:
                market = 0  # 深圳

            result = client.quotes(market=market, category=1, start=0, count=1)
            if not result.empty:
                row = result.iloc[0]
                print(f"最新价：{row.get('price', 'N/A')}")
                print(f"昨收：{row.get('last_close', 'N/A')}")
                print(f"今开：{row.get('open', 'N/A')}")
                print(f"最高：{row.get('high', 'N/A')}")
                print(f"最低：{row.get('low', 'N/A')}")
                print(f"成交量：{row.get('vol', 'N/A')} 手")
                print(f"成交额：{row.get('amount', 'N/A')} 元")
            else:
                print("暂无实时行情数据")
        except Exception as e:
            print(f"获取实时行情失败：{e}")

        # 2. K 线数据（日线）
        print("\n【K 线趋势分析】")
        try:
            kline_data = client.kdata(market=market, category=9, stock=stock_code)
            if not kline_data.empty and len(kline_data) > 0:
                recent = kline_data.tail(60)

                if len(recent) > 0:
                    current_price = recent["close"].iloc[-1]
                    price_60d_ago = (
                        recent["close"].iloc[0]
                        if len(recent) >= 60
                        else recent["close"].iloc[0]
                    )
                    change_60d = ((current_price - price_60d_ago) / price_60d_ago) * 100

                    # 计算均线
                    ma5 = recent["close"].rolling(5).mean().iloc[-1]
                    ma10 = recent["close"].rolling(10).mean().iloc[-1]
                    ma20 = recent["close"].rolling(20).mean().iloc[-1]

                    print(f"当前价格：{current_price}")
                    print(f"60 日前价格：{price_60d_ago:.2f}")
                    print(f"60 日涨跌幅：{change_60d:.2f}%")
                    print(f"MA5: {ma5:.2f}")
                    print(f"MA10: {ma10:.2f}")
                    print(f"MA20: {ma20:.2f}")

                    # 趋势判断
                    if current_price > ma5 > ma10 > ma20:
                        trend = "多头排列（强势）"
                    elif current_price < ma5 < ma10 < ma20:
                        trend = "空头排列（弱势）"
                    else:
                        trend = "震荡整理"
                    print(f"趋势判断：{trend}")
            else:
                print("无 K 线数据")
        except Exception as e:
            print(f"获取 K 线数据失败：{e}")

        # 3. 综合评估
        print("\n【综合评估】")
        print("注：详细财务数据和资金流向需要连接外部 API")
        print("建议结合公司财报、行业新闻等多维度信息进行分析")

        print("\n⚠️ 风险提示：以上数据仅供参考，不构成投资建议")

    except Exception as e:
        print(f"分析失败：{e}")


def main():
    """主函数"""
    print("=" * 60)
    print("📈 A 股股票深度分析 (mootdx)")
    print(f"分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 待分析的股票列表
    stocks = [
        {"code": "000559", "name": "万向钱潮"},
        {"code": "002600", "name": "领益智造"},
        {"code": "600460", "name": "士兰微"},
        {"code": "002407", "name": "多氟多"},
    ]

    for stock in stocks:
        get_stock_info(stock["code"], stock["name"])

    print("\n" + "=" * 60)
    print("✅ 全部分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
