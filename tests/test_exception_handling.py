from stock_monitor.utils.error_handler import safe_call


def test_safe_call_handles_exception():
    """测试 safe_call 是否能正确处理异常并返回默认值"""

    def raising_func():
        raise ValueError("测试异常")

    result = safe_call(raising_func, default_return="默认值")
    assert result == "默认值"


def test_safe_call_normal_return():
    """正常返回值应透传，不被修改"""
    result = safe_call(lambda: 42)
    assert result == 42


def test_safe_call_default_return_none():
    """异常时默认返回 None"""

    def failing():
        raise RuntimeError("boom")

    result = safe_call(failing)
    assert result is None


def test_safe_call_custom_exception_handler():
    """自定义异常处理器被调用且其返回值作为结果"""
    handler_called_with = []

    def my_handler(exc, error_type):
        handler_called_with.append((exc, error_type))
        return "handled"

    def raising():
        raise ValueError("test")

    result = safe_call(raising, exception_handler=my_handler)

    assert result == "handled"
    assert len(handler_called_with) == 1
    assert isinstance(handler_called_with[0][0], ValueError)
    assert handler_called_with[0][1] == "validation"


def test_safe_call_passes_args_and_kwargs():
    """safe_call 应透传位置参数和关键字参数"""

    def add(a, b, extra=0):
        return a + b + extra

    assert safe_call(add, 1, 2) == 3
    assert safe_call(add, 1, 2, extra=10) == 13
