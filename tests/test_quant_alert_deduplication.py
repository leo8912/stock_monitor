"""
量化推送防抖动逻辑测试脚本
用于验证冷却机制、状态变更检测和信号合并功能
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from stock_monitor.core.workers.quant_worker import QuantWorker


class MockFetcher:
    """模拟股票数据获取器"""

    def __init__(self):
        self.mootdx_client = None
        self.name_registry = MockNameRegistry()


class MockNameRegistry:
    """模拟股票名称注册表"""

    def get_name(self, symbol: str) -> str:
        names = {
            "sh600519": "贵州茅台",
            "sz000858": "五粮液",
            "sh600030": "中信证券",
        }
        return names.get(symbol, "未知股票")


def test_cooldown_mechanism():
    """测试1：冷却机制"""
    print("\n" + "=" * 60)
    print("测试1：信号冷却机制")
    print("=" * 60)

    worker = QuantWorker(MockFetcher(), wecom_webhook="")
    worker.config = {
        "quant_alert_cooldown": 60,  # 60秒冷却
        "quant_alert_score_threshold": 2,
        "quant_alert_merge_enabled": True,
    }

    symbol = "sh600519"
    sig_name = "日线:MACD底背离"

    # 首次检测 - 应该允许
    should_push, reason = worker._should_push_signal(symbol, sig_name, 3)
    print(f"✓ 首次检测: should_push={should_push}, reason={reason}")
    assert should_push is True, "首次检测应该允许推送"

    # 更新状态
    worker._update_signal_state(symbol, sig_name, 3)

    # 5秒后检测 - 应该在冷却中
    time.sleep(0.1)  # 模拟时间流逝（实际测试中可调整）
    should_push, reason = worker._should_push_signal(symbol, sig_name, 3)
    print(f"✓ 5秒后检测: should_push={should_push}, reason={reason}")
    # 注意：由于实际只过了0.1秒，仍在冷却期内
    assert should_push is False or "冷却" in reason, "冷却期内应阻止推送"

    print("✅ 测试1通过：冷却机制正常工作\n")


def test_score_change_detection():
    """测试2：评分变化检测"""
    print("\n" + "=" * 60)
    print("测试2：评分变化检测")
    print("=" * 60)

    worker = QuantWorker(MockFetcher(), wecom_webhook="")
    worker.config = {
        "quant_alert_cooldown": 3600,  # 1小时冷却
        "quant_alert_score_threshold": 2,  # 变化阈值2分
        "quant_alert_merge_enabled": True,
    }

    symbol = "sh600519"
    sig_name = "日线:MACD底背离"

    # 首次推送（评分+3）
    worker._update_signal_state(symbol, sig_name, 3)
    print("✓ 初始状态: 评分=+3")

    # 评分小幅变化（+3 → +4，变化1分 < 阈值2分）- 不应推送
    should_push, reason = worker._should_push_signal(symbol, sig_name, 4)
    print(f"✓ 评分+3→+4: should_push={should_push}, reason={reason}")
    assert should_push is False, "小幅变化不应触发推送"

    # 评分大幅变化（+3 → +5，变化2分 >= 阈值2分）- 应推送
    should_push, reason = worker._should_push_signal(symbol, sig_name, 5)
    print(f"✓ 评分+3→+5: should_push={should_push}, reason={reason}")
    assert should_push is True, "大幅变化应触发推送"
    assert "显著变化" in reason, "原因应包含'显著变化'"

    print("✅ 测试2通过：评分变化检测正常\n")


def test_signal_merge():
    """测试3：信号合并推送"""
    print("\n" + "=" * 60)
    print("测试3：信号合并推送")
    print("=" * 60)

    worker = QuantWorker(MockFetcher(), wecom_webhook="")
    worker.config = {
        "quant_alert_cooldown": 1800,
        "quant_alert_score_threshold": 2,
        "quant_alert_merge_enabled": True,
    }

    symbol = "sh600519"
    stock_name = "贵州茅台"

    # 模拟多个信号
    signals_data = [
        {
            "sig_name": "日线:MACD底背离",
            "score": 3,
            "audit": {"label": "🟢 优质", "reasons": ["ROE稳定"], "score_offset": 1},
            "p_info": {"price": 1800.50, "pct": 1.2},
            "is_priority": False,
            "is_confluence": False,
        },
        {
            "sig_name": "30分钟:OBV碎步吸筹",
            "score": 2,
            "audit": {"label": "🟢 优质", "reasons": ["ROE稳定"], "score_offset": 1},
            "p_info": {"price": 1800.50, "pct": 1.2},
            "is_priority": False,
            "is_confluence": False,
        },
    ]

    # 执行合并
    merged = worker._merge_signals_for_symbol(symbol, stock_name, signals_data)

    print(f"✓ 合并标题: {merged['title']}")
    print(f"✓ 信号摘要: {merged['signals_text']}")
    print(f"✓ 综合强度: {merged['max_score']}")

    assert "贵州茅台" in merged["title"], "标题应包含股票名称"
    assert "2 个技术信号" in merged["signals_text"], "应显示信号数量"
    assert merged["max_score"] == 3, "应取最高分"

    print("✅ 测试3通过：信号合并功能正常\n")


def test_cache_persistence():
    """测试4：缓存持久化"""
    print("\n" + "=" * 60)
    print("测试4：缓存持久化（加载/保存）")
    print("=" * 60)

    worker = QuantWorker(MockFetcher(), wecom_webhook="")

    # 模拟一些状态
    worker._signal_states = {
        ("sh600519", "日线:MACD底背离"): {
            "last_score": 3,
            "last_push_ts": time.time(),
        },
        ("sz000858", "30分钟:OBV碎步吸筹"): {
            "last_score": 2,
            "last_push_ts": time.time() - 100,
        },
    }

    # 保存缓存
    worker._save_signal_cache()
    print("✓ 缓存已保存")

    # 创建新实例并加载
    worker2 = QuantWorker(MockFetcher(), wecom_webhook="")
    worker2._load_signal_cache()
    print("✓ 缓存已加载")

    # 验证数据完整性
    assert (
        len(worker2._signal_states) == 2
    ), f"应有2个状态，实际{len(worker2._signal_states)}"
    assert ("sh600519", "日线:MACD底背离") in worker2._signal_states
    assert worker2._signal_states[("sh600519", "日线:MACD底背离")]["last_score"] == 3

    print("✅ 测试4通过：缓存持久化正常\n")


def main():
    """运行所有测试"""
    print("\n" + "🧪 开始量化推送防抖动测试套件")
    print("=" * 60)

    try:
        test_cooldown_mechanism()
        test_score_change_detection()
        test_signal_merge()
        test_cache_persistence()

        print("\n" + "=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n核心功能验证：")
        print("  ✅ 信号冷却机制")
        print("  ✅ 评分变化检测")
        print("  ✅ 信号合并推送")
        print("  ✅ 缓存持久化")
        print("\n建议下一步：")
        print("  1. 在真实环境中观察推送频率")
        print("  2. 根据实际需求调整 config.json 中的参数")
        print("  3. 查看日志确认防抖动逻辑执行情况")

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
