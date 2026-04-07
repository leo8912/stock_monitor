"""
异常处理框架单元测试 - P1改进
"""

import unittest
from unittest.mock import MagicMock

from stock_monitor.utils.exception_handler import (
    DataValidationException,
    ExceptionCategory,
    ExternalAPIException,
    NetworkException,
    classify_exception,
    handle_exception,
    safe_call,
)


class TestExceptionClassification(unittest.TestCase):
    """异常分类测试"""

    def test_classify_network_exception(self):
        """测试网络异常分类"""
        exc = TimeoutError("连接超时")
        category = classify_exception(exc)
        self.assertEqual(category, ExceptionCategory.NETWORK)

    def test_classify_data_error(self):
        """测试数据错误分类"""
        exc = ValueError("无效的数据格式")
        category = classify_exception(exc)
        self.assertEqual(category, ExceptionCategory.DATA_ERROR)

    def test_classify_type_error(self):
        """测试类型错误分类"""
        exc = TypeError("类型不匹配")
        category = classify_exception(exc)
        self.assertEqual(category, ExceptionCategory.DATA_ERROR)

    def test_classify_unknown_exception(self):
        """测试未知异常分类"""
        exc = RuntimeError("某个运行时错误")
        category = classify_exception(exc)
        self.assertEqual(category, ExceptionCategory.UNKNOWN)


class TestApplicationExceptions(unittest.TestCase):
    """应用异常类测试"""

    def test_network_exception(self):
        """测试网络异常"""
        original_exc = TimeoutError("连接超时")
        exc = NetworkException("获取股票数据失败", original_exc, symbol="SH600000")

        self.assertEqual(exc.category, ExceptionCategory.NETWORK)
        self.assertIn("NETWORK", str(exc))
        self.assertIn("SH600000", str(exc))

    def test_data_validation_exception(self):
        """测试数据验证异常"""
        exc = DataValidationException("股票价格无效")
        self.assertEqual(exc.category, ExceptionCategory.DATA_ERROR)

    def test_external_api_exception(self):
        """测试外部API异常"""
        exc = ExternalAPIException("API返回错误码")
        self.assertEqual(exc.category, ExceptionCategory.EXTERNAL_API)


class TestSafeCallDecorator(unittest.TestCase):
    """safe_call装饰器测试"""

    def test_safe_call_success(self):
        """测试成功调用"""

        @safe_call()
        def successful_func():
            return "success"

        result = successful_func()
        self.assertEqual(result, "success")

    def test_safe_call_default_return(self):
        """测试异常返回默认值"""

        @safe_call(default_return=0)
        def failing_func():
            raise ValueError("错误")

        result = failing_func()
        self.assertEqual(result, 0)

    def test_safe_call_with_retries(self):
        """测试重试机制"""
        call_count = 0

        @safe_call(max_retries=2, default_return=None)
        def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("连接失败")
            return "success"

        # 装饰器会重试两次，第三次成功
        result = retry_func()
        # 因为第3次调用成功，返回成功结果
        self.assertEqual(result, "success")

    def test_safe_call_with_fallback(self):
        """测试降级策略"""

        @safe_call(default_return=None, fallback_strategy=lambda: "fallback_result")
        def failing_func():
            raise RuntimeError("错误")

        result = failing_func()
        self.assertEqual(result, "fallback_result")

    def test_safe_call_with_exception_callback(self):
        """测试异常回调"""
        callback_called = False
        callback_args = {}

        def exception_callback(func_name, exc, attempt, max_retries):
            nonlocal callback_called, callback_args
            callback_called = True
            callback_args = {
                "func_name": func_name,
                "exc": exc,
                "attempt": attempt,
                "max_retries": max_retries,
            }

        @safe_call(default_return=0, on_exception_callback=exception_callback)
        def failing_func():
            raise ValueError("错误")

        result = failing_func()

        self.assertTrue(callback_called)
        self.assertEqual(callback_args["func_name"], "failing_func")
        self.assertIsInstance(callback_args["exc"], ValueError)
        self.assertEqual(result, 0)

    def test_safe_call_specific_exceptions(self):
        """测试捕获特定异常"""

        @safe_call(default_return="caught", catch_exceptions=(ValueError, TypeError))
        def raising_value_error():
            raise ValueError("这应该被捕获")

        result = raising_value_error()
        self.assertEqual(result, "caught")

    def test_safe_call_uncaught_exception(self):
        """测试未捕获的异常"""

        @safe_call(default_return="caught", catch_exceptions=(ValueError,))
        def raising_runtime_error():
            raise RuntimeError("这不应该被捕获")

        # 由于RuntimeError不在catch_exceptions中，应该被抛出
        with self.assertRaises(RuntimeError):
            raising_runtime_error()


class TestHandleException(unittest.TestCase):
    """handle_exception函数测试"""

    def test_handle_network_exception(self):
        """测试处理网络异常"""
        func = MagicMock(__name__="test_func")
        exc = TimeoutError("连接超时")

        def fallback():
            return "fallback_data"

        result = handle_exception(
            func, exc, default_return=None, fallback_strategy=fallback
        )

        self.assertEqual(result, "fallback_data")

    def test_handle_exception_with_context(self):
        """测试带上下文的异常处理"""
        func = MagicMock(__name__="fetch_data")
        exc = ValueError("数据格式错误")
        context = {"symbol": "SH600000", "attempt": 1}

        result = handle_exception(func, exc, context=context, default_return=None)

        self.assertIsNone(result)


class TestExceptionIntegration(unittest.TestCase):
    """异常处理集成测试"""

    def test_network_retry_and_fallback(self):
        """测试网络异常重试和降级"""
        attempt_counter = {"count": 0}

        def make_api_call():
            attempt_counter["count"] += 1
            if attempt_counter["count"] < 2:
                raise ConnectionError("API连接失败")
            return {"data": "fresh"}

        def fallback_strategy():
            return {"data": "cached"}

        @safe_call(
            max_retries=1,
            fallback_strategy=fallback_strategy,
            catch_exceptions=(ConnectionError,),
        )
        def decorated_api_call():
            return make_api_call()

        # 重试一次，第二次成功，返回fresh数据
        result = decorated_api_call()
        self.assertEqual(result, {"data": "fresh"})

    def test_data_validation_with_logging(self):
        """测试数据验证异常记录"""

        @safe_call(default_return=None)
        def validate_stock_price(price):
            if not isinstance(price, (int, float)):
                raise DataValidationException(
                    "股票价格必须是数字", context={"price": price}
                )
            if price < 0:
                raise DataValidationException("股票价格不能为负")
            return price

        # 测试有效价格
        result = validate_stock_price(10.5)
        self.assertEqual(result, 10.5)

        # 测试无效价格（异常被safe_call捕获）
        result = validate_stock_price("invalid")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
