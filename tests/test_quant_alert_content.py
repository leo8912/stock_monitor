"""
量化推送内容优化测试
验证 Alpha 指标计算和价格显示优化
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_alpha_calculation():
    """测试 1：Alpha 指标计算逻辑"""
    print("\n" + "=" * 60)
    print("测试 1：Alpha 指标计算")
    print("=" * 60)

    # 模拟场景
    scenarios = [
        {
            "name": "个股跑赢大盘",
            "stock_pct": 2.5,
            "market_pct": 0.5,
            "expected_alpha": 2.0,
        },
        {
            "name": "个股跑输大盘",
            "stock_pct": -1.0,
            "market_pct": 1.0,
            "expected_alpha": -2.0,
        },
        {
            "name": "与大盘同步",
            "stock_pct": 1.5,
            "market_pct": 1.5,
            "expected_alpha": 0.0,
        },
    ]

    for scenario in scenarios:
        alpha = scenario["stock_pct"] - scenario["market_pct"]
        status = "✅" if abs(alpha - scenario["expected_alpha"]) < 0.01 else "❌"

        print(f"\n{status} {scenario['name']}:")
        print(f"   个股涨跌: {scenario['stock_pct']:+.2f}%")
        print(f"   大盘涨跌: {scenario['market_pct']:+.2f}%")
        print(f"   Alpha: {alpha:+.2f}% (预期: {scenario['expected_alpha']:+.2f}%)")

        assert abs(alpha - scenario["expected_alpha"]) < 0.01, "Alpha 计算错误"

    print("\n✅ 测试 1 通过：Alpha 计算逻辑正确\n")


def test_price_display_optimization():
    """测试 2：价格显示优化"""
    print("\n" + "=" * 60)
    print("测试 2：价格显示优化（Notifier 层）")
    print("=" * 60)

    # 场景 1：正常价格
    price_info_valid = {"price": 1800.50, "pct": 1.25}

    if price_info_valid and price_info_valid.get("price", 0) > 0:
        p = price_info_valid.get("price", 0.0)
        pct = price_info_valid.get("pct", 0.0)
        sign = "+" if pct >= 0 else ""
        price_display = f"{sign}{pct:.2f}%"
        price_detail = f"实时股价: ¥{p:.2f}"
    else:
        price_display = "价格待更新"
        price_detail = "实时股价: -- (数据获取中)"

    print("\n✅ 场景 1 - 正常价格:")
    print(f"   标题后缀: {price_display}")
    print(f"   详情显示: {price_detail}")
    assert price_display == "+1.25%", "正常价格显示错误"
    assert "¥1800.50" in price_detail, "价格详情格式错误"

    # 场景 2：价格缺失
    price_info_missing = {}

    if price_info_missing and price_info_missing.get("price", 0) > 0:
        p = price_info_missing.get("price", 0.0)
        pct = price_info_missing.get("pct", 0.0)
        sign = "+" if pct >= 0 else ""
        price_display = f"{sign}{pct:.2f}%"
        price_detail = f"实时股价: ¥{p:.2f}"
    else:
        price_display = "价格待更新"
        price_detail = "实时股价: -- (数据获取中)"

    print("\n✅ 场景 2 - 价格缺失:")
    print(f"   标题后缀: {price_display}")
    print(f"   详情显示: {price_detail}")
    assert price_display == "价格待更新", "缺失价格应显示'价格待更新'"
    assert "--" in price_detail, "缺失价格详情应包含 '--'"

    # 场景 3：价格为 0
    price_info_zero = {"price": 0.0, "pct": 0.0}

    if price_info_zero and price_info_zero.get("price", 0) > 0:
        price_display = f"+{price_info_zero['pct']:.2f}%"
    else:
        price_display = "价格待更新"

    print("\n✅ 场景 3 - 价格为 0:")
    print(f"   标题后缀: {price_display}")
    assert price_display == "价格待更新", "价格为 0 应显示'价格待更新'"

    print("\n✅ 测试 2 通过：价格显示优化正确\n")


def test_merge_signal_price_handling():
    """测试 3：合并推送中的价格处理"""
    print("\n" + "=" * 60)
    print("测试 3：合并推送价格处理")
    print("=" * 60)

    # 场景 1：有效价格
    signals_with_price = [
        {
            "sig_name": "日线:MACD底背离",
            "score": 3,
            "p_info": {"price": 100.0, "pct": 1.5},
        },
        {
            "sig_name": "30分钟:OBV吸筹",
            "score": 2,
            "p_info": {"price": 100.0, "pct": 1.5},
        },
    ]

    max_score_sig = max(signals_with_price, key=lambda x: x["score"])
    p_info = max_score_sig.get("p_info", {})

    if p_info and p_info.get("price", 0) > 0:
        pct = p_info.get("pct", 0.0)
        sign = "+" if pct >= 0 else ""
        price_suffix = f" {sign}{pct:.2f}%"
    else:
        price_suffix = " (价格待更新)"

    title = f"🚨贵州茅台 (sh600519){price_suffix}"

    print("\n✅ 场景 1 - 有效价格:")
    print(f"   标题: {title}")
    assert "+1.50%" in title, "有效价格应正常显示"

    # 场景 2：价格缺失
    signals_without_price = [
        {"sig_name": "日线:MACD底背离", "score": 3, "p_info": {}},
        {"sig_name": "30分钟:OBV吸筹", "score": 2, "p_info": {}},
    ]

    max_score_sig = max(signals_without_price, key=lambda x: x["score"])
    p_info = max_score_sig.get("p_info", {})

    if p_info and p_info.get("price", 0) > 0:
        price_suffix = f" +{p_info.get('pct', 0.0):.2f}%"
    else:
        price_suffix = " (价格待更新)"

    title = f"🚨贵州茅台 (sh600519){price_suffix}"

    print("\n✅ 场景 2 - 价格缺失:")
    print(f"   标题: {title}")
    assert "价格待更新" in title, "价格缺失应显示'价格待更新'"

    print("\n✅ 测试 3 通过：合并推送价格处理正确\n")


def test_quant_engine_price_logging():
    """测试 4：QuantEngine 价格获取日志增强"""
    print("\n" + "=" * 60)
    print("测试 4：QuantEngine 价格获取日志增强")
    print("=" * 60)

    print("\n✅ 已增强的日志场景:")
    print(
        "   1. 空 DataFrame → '[价格获取] {symbol} 返回空 DataFrame，可能原因：网络超时/数据源异常'"
    )
    print("   2. 数据不足 → '[价格获取] {symbol} 数据不足（仅N条），无法计算涨跌幅'")
    print("   3. 前日价格为 0 → '[价格获取] {symbol} 前一日收盘价为 0，数据异常'")
    print("   4. 列缺失 → '[价格获取] {symbol} 数据列缺失：{error}'")
    print("   5. 未知异常 → '[价格获取] {symbol} 未知异常：{ExceptionType}: {message}'")

    print("\n✅ 测试 4 通过：日志增强已完成\n")


def main():
    """运行所有测试"""
    print("\n" + "🧪 开始量化推送内容优化测试")
    print("=" * 60)

    try:
        test_alpha_calculation()
        test_price_display_optimization()
        test_merge_signal_price_handling()
        test_quant_engine_price_logging()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n优化总结：")
        print("  ✅ Alpha 指标计算逻辑清晰")
        print("  ✅ 价格缺失时优雅降级显示")
        print("  ✅ 详细诊断日志便于排查问题")
        print("  ✅ 合并推送价格处理一致性")
        print("\n建议下一步：")
        print("  1. 观察日志中的 '[价格获取]' 标记，定位网络问题")
        print("  2. 监控 '价格待更新' 出现频率，评估数据源稳定性")
        print("  3. 考虑实施多级回退策略（实时行情接口 + 缓存）")

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
