import os
import sys

# 添加项目路径
sys.path.append(os.getcwd())

from mootdx.quotes import factory

from stock_monitor.core.quant_engine import QuantEngine


def test_auction():
    client = factory(type="tdx")
    engine = QuantEngine(client)

    # 测试代码：平安银行
    code = "sz000001"

    print(f"开始测试 {code} 竞价数据获取...")

    # 模拟获取 5 日均量
    avg_vol = engine.get_five_day_avg_minute_volume(code)
    print(f"5日均量: {avg_vol:.2f}")

    # 获取竞价数据
    res = engine.fetch_call_auction_data(code)
    print(f"竞价结果: {res}")

    if res.get("intensity", 0) > 0:
        print("✅ 竞价数据获取成功")
    else:
        print("⚠️ 竞价数据为 0 (可能当前非交易时段且无缓存)")


if __name__ == "__main__":
    try:
        test_auction()
    except Exception as e:
        print(f"测试失败: {e}")
