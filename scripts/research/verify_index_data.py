import os
import sys

# 确保能导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_monitor.core.container import container
from stock_monitor.core.quant_engine import QuantEngine


def verify_data():
    engine = container.get(QuantEngine)

    print("正在拉取上证指数 (sh000001) 数据...")
    df = engine.fetch_bars("sh000001", category=9, offset=1)

    if df is not None and not df.empty:
        price = df.iloc[-1]["close"]
        print(f"sh000001 最新收盘价: {price}")
        if price > 2000:
            print("✅ 验证成功：已正确获取上证指数点位数据。")
        else:
            print(f"❌ 验证失败：价格 {price} 疑似仍为平安银行。")
    else:
        print("❌ 验证失败：未能获取到数据。")


if __name__ == "__main__":
    verify_data()
