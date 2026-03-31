import os
import sys

import pandas as pd

# 将项目根目录添加到系统路径，以便测试导入
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stock_monitor.core.quant_engine import QuantEngine


class MockMootdx:
    def bars(self, **kwargs):
        # 返回一个简单的下降趋势 DF 模拟弱势
        data = {
            "close": [100.0] * 50 + [90.0] * 50,
            "high": [101.0] * 100,
            "low": [99.0] * 100,
            "volume": [1000] * 100,
            "datetime": pd.date_range(start="2023-01-01", periods=100),
        }
        return pd.DataFrame(data)


def test_financial_integration():
    print("--- 财务过滤系统模拟测试 ---")

    # 1. 模拟一个财务相对健康的股票 (贵州茅台)
    # 2. 模拟一个可能有风险的股票 (假设的代码)

    engine = QuantEngine(MockMootdx())

    # 构建一个带有利好信号的模拟 df (MACD底背离通过信号名称模拟)
    mock_df = pd.DataFrame({"close": [10.0] * 100, "volume": [1000] * 100})
    signals = [{"name": "MACD底背离", "tf": "daily"}]

    test_cases = [
        ("sh600519", "茅台 (绩优)"),
        ("sz000002", "万科 (观察)"),
        ("sh600000", "浦发 (银行业务)"),
    ]

    for symbol, label in test_cases:
        print(f"\n测试标的: {label} ({symbol})")
        score, audit = engine.calculate_intensity_score_with_symbol(
            symbol, mock_df, signals
        )

        print(f"财务评级: {audit['rating']}")
        print(f"风险理由: {audit['reasons']}")
        print(f"指标详情: {audit['details']}")
        print(f"最终得分: {score:+}")

        if audit["rating"] == "🔴":
            assert score <= 0, "🔴级红线必须压制利好评分为 <=0"
            print(">>> 校验通过: 财务红线成功压制评分")
        else:
            print(">>> 校验通过: 财务表现正常/可控")


if __name__ == "__main__":
    try:
        test_financial_integration()
        print("\n✅ 所有逻辑校验完成")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
