from stock_monitor.utils.error_handler import safe_call


def test_safe_call_handles_exception():
    """测试 safe_call 是否能正确处理异常并返回默认值"""

    def raising_func():
        raise ValueError("测试异常")

    result = safe_call(raising_func, default_return="默认值")
    assert result == "默认值"
