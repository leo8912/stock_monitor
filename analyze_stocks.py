#!/usr/bin/env python3
"""
股票分析脚本 - 分析万向钱潮、领益智造、士兰微、多氟多
"""

from datetime import datetime

import akshare as ak
import pandas as pd


def analyze_stock(stock_code: str, stock_name: str):
    """分析单只股票"""
    print(f"\n{'='*60}")
    print(f"📊 {stock_name} ({stock_code})")
    print(f"{'='*60}\n")

    try:
        # 1. 实时行情（改用个股查询，更稳定）
        print("【实时行情】")
        try:
            # 获取沪深 A 股所有股票实时行情
            spot_data = ak.stock_zh_a_spot_em()
            stock_spot = spot_data[spot_data["代码"] == stock_code]
        except Exception:
            # 如果批量接口失败，尝试直接获取个股信息
            print("批量接口失败，尝试直接获取个股数据...")
            stock_spot = pd.DataFrame()

        if not stock_spot.empty:
            row = stock_spot.iloc[0]
            latest_price = float(row["最新价"]) if pd.notna(row["最新价"]) else None
            change_pct = float(row["涨跌幅"]) if pd.notna(row["涨跌幅"]) else None
            change_amt = float(row["涨跌额"]) if pd.notna(row["涨跌额"]) else None
            volume = int(row["成交量"]) if pd.notna(row["成交量"]) else None
            amount = float(row["成交额"]) if pd.notna(row["成交额"]) else None
            amplitude = float(row["振幅"]) if pd.notna(row["振幅"]) else None
            turnover = float(row["换手率"]) if pd.notna(row["换手率"]) else None
            volume_ratio = float(row["量比"]) if pd.notna(row["量比"]) else None
            pe_dynamic = (
                float(row["市盈率 - 动态"]) if pd.notna(row["市盈率 - 动态"]) else None
            )
            pb = float(row["市净率"]) if pd.notna(row["市净率"]) else None

            print(f"最新价：{latest_price}")
            print(f"涨跌幅：{change_pct}%")
            print(f"涨跌额：{change_amt}")
            print(f"成交量：{volume} 手")
            print(f"成交额：{amount/10000:.2f} 万元" if amount else "N/A")
            print(f"振幅：{amplitude}%")
            print(f"换手率：{turnover}%")
            print(f"量比：{volume_ratio}")
            print(f"市盈率 (动态):{pe_dynamic}")
            print(f"市净率：{pb}")
        else:
            print("未找到实时行情数据（网络可能不稳定）")

        # 2. 近期 K 线（近 60 日）
        print("\n【近 60 日 K 线趋势】")
        kline_data = ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq")
        if len(kline_data) > 0:
            recent = kline_data.tail(60)

            # 计算均线
            ma5 = recent["收盘"].rolling(5).mean().iloc[-1]
            ma10 = recent["收盘"].rolling(10).mean().iloc[-1]
            ma20 = recent["收盘"].rolling(20).mean().iloc[-1]

            current_price = recent["收盘"].iloc[-1]
            price_60d_ago = recent["收盘"].iloc[0]
            change_60d = ((current_price - price_60d_ago) / price_60d_ago) * 100

            print(f"当前价格：{current_price}")
            print(f"60 日前价格：{price_60d_ago}")
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

        # 3. 基本面数据
        print("\n【基本面指标】")
        try:
            financial_data = ak.stock_financial_abstract(symbol=stock_code)
            if not financial_data.empty:
                latest = financial_data.iloc[0]
                print(f"营业收入：{latest.get('营业总收入', 'N/A')}")
                print(f"净利润：{latest.get('净利润', 'N/A')}")
                print(f"ROE: {latest.get('净资产收益率', 'N/A')}")
                print(f"毛利率：{latest.get('销售毛利率', 'N/A')}")
                print(f"资产负债率：{latest.get('资产负债率', 'N/A')}")
            else:
                print("暂无财务数据")
        except Exception as e:
            print(f"获取财务数据失败：{e}")

        # 4. 资金流向
        print("\n【资金流向】")
        try:
            flow_data = ak.stock_individual_fund_flow(
                symbol=stock_code,
                market="sz" if stock_code.startswith(("000", "002", "300")) else "sh",
            )
            if not flow_data.empty:
                latest = flow_data.iloc[0]
                print(f"主力净流入：{latest.get('主力净流入-净额', 'N/A')} 万元")
                print(f"大单净流入：{latest.get('大单净流入-净额', 'N/A')} 万元")
                print(f"中单净流入：{latest.get('中单净流入-净额', 'N/A')} 万元")
                print(f"小单净流入：{latest.get('小单净流入-净额', 'N/A')} 万元")

                # 判断资金流向
                main_force = float(latest.get("主力净流入 - 净额", 0))
                if main_force > 0:
                    flow_trend = f"主力资金流入 ({main_force}万元)"
                else:
                    flow_trend = f"主力资金流出 ({main_force}万元)"
                print(f"资金流向：{flow_trend}")
            else:
                print("无资金流向数据")
        except Exception as e:
            print(f"获取资金流向失败：{e}")

        # 5. 综合评估
        print("\n【综合评估】")
        if not stock_spot.empty:
            row = stock_spot.iloc[0]
            pe = float(row["市盈率 - 动态"]) if pd.notna(row["市盈率 - 动态"]) else None
            pb = float(row["市净率"]) if pd.notna(row["市净率"]) else None
            turnover = float(row["换手率"]) if pd.notna(row["换手率"]) else None

            # 估值判断
            if pe and pe < 20:
                valuation = "低估"
            elif pe and pe < 40:
                valuation = "合理"
            elif pe and pe >= 40:
                valuation = "高估"
            else:
                valuation = "无法评估"

            # 活跃度
            if turnover and turnover > 10:
                activity = "非常活跃"
            elif turnover and turnover > 5:
                activity = "较活跃"
            else:
                activity = "一般"

            print(f"估值水平：{valuation} (PE: {pe})")
            print(f"交易活跃度：{activity} (换手率：{turnover}%)")
            print(f"市净率：{pb}")

        print("\n⚠️ 风险提示：以上数据仅供参考，不构成投资建议")

    except Exception as e:
        print(f"分析失败：{e}")


def main():
    """主函数"""
    print("=" * 60)
    print("📈 A 股股票深度分析")
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
        analyze_stock(stock["code"], stock["name"])

    print("\n" + "=" * 60)
    print("✅ 全部分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
