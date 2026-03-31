import os
import sys

import pandas as pd

# 将项目根目录加入路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stock_monitor.core.market_manager import market_manager
from stock_monitor.core.quant_engine import QuantEngine


def test_sentiment_logic():
    print("=== 市场环境因子逻辑测试 ===")

    # 模拟 mootdx 客户端
    class MockClient:
        def bars(self, **kwargs):
            return pd.DataFrame()

        def quotes(self, **kwargs):
            return pd.DataFrame()

    engine = QuantEngine(MockClient())

    # 1. 测试普涨行情 (Up > 70%)
    market_manager.update_sentiment(up=4000, down=1000, flat=500, total=5500)
    factor, desc = engine.calculate_market_sentiment_factor()
    print(
        f"【普涨测试】比例: {market_manager.get_sentiment().up_ratio:.2%}, 因子: {factor}, 描述: {desc}"
    )
    assert factor == 1.0

    # 2. 测试中性行情 (50%)
    market_manager.update_sentiment(up=2500, down=2500, flat=500, total=5500)
    factor, desc = engine.calculate_market_sentiment_factor()
    print(
        f"【中性测试】比例: {market_manager.get_sentiment().up_ratio:.2%}, 因子: {factor}, 描述: {desc}"
    )
    assert factor == 0.0

    # 3. 测试恐慌普跌 (Up < 20%)
    market_manager.update_sentiment(up=500, down=4500, flat=500, total=5500)
    factor, desc = engine.calculate_market_sentiment_factor()
    print(
        f"【恐慌测试】比例: {market_manager.get_sentiment().up_ratio:.2%}, 因子: {factor}, 描述: {desc}"
    )
    assert factor == -3.0

    # 4. 测试综合评分压制
    # 假设技术面 +3 分，但处于恐慌行情 (-3)
    # 预期最终得分应被压制到 <= -1 (根据熔断逻辑)
    mock_df = pd.DataFrame({"close": [10] * 10})
    mock_signals = [{"name": "MACD底背离"}]  # 基础分 +3

    final_score, audit = engine.calculate_intensity_score_with_symbol(
        "sh600000", mock_df, mock_signals
    )
    print(f"【评分压制测试】技术面:+3, 市场:-3, 最终得分: {final_score}")
    assert final_score <= -1

    print("\n✅ 所有逻辑校验通过！")


if __name__ == "__main__":
    test_sentiment_logic()
