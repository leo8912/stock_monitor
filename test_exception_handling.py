from stock_monitor.utils.error_handler import safe_call

def test_func():
    raise ValueError('测试异常')

result = safe_call(test_func, default_return='默认值')
print('异常处理结果:', result)