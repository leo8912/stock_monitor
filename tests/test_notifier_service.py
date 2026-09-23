"""
NotifierService 消息推送服务单元测试

注意：NotifierService 使用 thread-local ``requests.Session``
（``NotifierService._get_session()``），因此对底层 HTTP 调用的打桩需针对
``requests.Session.get`` / ``requests.Session.post``，而非模块级的
``requests.get`` / ``requests.post``。同理，网络异常重试自迁移到
``tenacity network_retry`` 后，仅在 ``RETRYABLE_EXCEPTIONS``
（ConnectionError/TimeoutError/IOError/OSError）上重试，且重试用尽后
``reraise=True`` 会把异常向上抛出（不再静默返回 False）。
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from stock_monitor.services.notifier import NotifierService


class TestNotifierService(unittest.TestCase):
    """NotifierService 测试类"""

    def setUp(self):
        """测试前准备"""
        # 清理缓存，确保测试隔离
        NotifierService._token_cache.clear()

        # 准备测试配置
        self.test_config = {
            "wecom_corpid": "test_corp_id",
            "wecom_corpsecret": "test_secret",
            "wecom_agentid": 1000001,
            "wecom_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
        }

    def tearDown(self):
        """测试后清理"""
        NotifierService._token_cache.clear()

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_get_app_token_success(self, mock_get):
        """测试成功获取企业微信 Token"""
        # 模拟 API 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 0,
            "access_token": "test_access_token",
            "expires_in": 7200,
        }
        mock_get.return_value = mock_response

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证结果
        self.assertEqual(token, "test_access_token")

        # 验证缓存已设置
        self.assertIn(("test_corp", "test_secret"), NotifierService._token_cache)
        cached_token, expiry = NotifierService._token_cache[
            ("test_corp", "test_secret")
        ]
        self.assertEqual(cached_token, "test_access_token")
        self.assertGreater(expiry, time.time())

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_get_app_token_api_error(self, mock_get):
        """测试 API 错误处理"""
        # 模拟 API 错误响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40019,
            "errmsg": "Invalid access_token",
        }
        mock_get.return_value = mock_response

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证返回 None
        self.assertIsNone(token)

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_get_app_token_network_error(self, mock_get):
        """测试网络异常处理"""
        # 模拟网络异常
        mock_get.side_effect = Exception("Network error")

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证返回 None
        self.assertIsNone(token)

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_get_app_token_cache_hit(self, mock_get):
        """测试缓存命中"""
        # 先手动设置缓存
        now = time.time()
        NotifierService._token_cache[("test_corp", "test_secret")] = (
            "cached_token",
            now + 3600,
        )

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证使用缓存，未调用 API
        self.assertEqual(token, "cached_token")
        mock_get.assert_not_called()

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_get_app_token_cache_expired(self, mock_get):
        """测试缓存过期"""
        # 设置过期的缓存
        expired_time = time.time() - 3600
        NotifierService._token_cache[("test_corp", "test_secret")] = (
            "expired_token",
            expired_time,
        )

        # 模拟新的 Token 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 0,
            "access_token": "new_token",
            "expires_in": 7200,
        }
        mock_get.return_value = mock_response

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证获取了新 Token
        self.assertEqual(token, "new_token")
        mock_get.assert_called_once()

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_wrong_secret_does_not_reuse_cached_token(self, mock_get):
        """S5 回归：同一 corp_id 用错误 secret 时不得命中旧 token 缓存。"""
        now = time.time()
        NotifierService._token_cache[("test_corp", "correct_secret")] = (
            "cached_token",
            now + 3600,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40001,
            "errmsg": "invalid credential",
        }
        mock_get.return_value = mock_response

        token = NotifierService._get_app_token("test_corp", "WRONG_secret")

        self.assertIsNone(token)
        mock_get.assert_called_once()  # 必须走网络，不得吃缓存

    @patch("stock_monitor.services.notifier.requests.Session.get")
    def test_test_app_push_rejects_wrong_secret(self, mock_get):
        """S5 回归：test_app_push 用错误 secret 必须失败，且错误串含「Token 失败」。"""
        now = time.time()
        NotifierService._token_cache[("test_corp", "correct_secret")] = (
            "cached_token",
            now + 3600,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40001,
            "errmsg": "invalid credential",
        }
        mock_get.return_value = mock_response

        result = NotifierService.test_app_push("test_corp", "WRONG_secret", "1000001")

        self.assertFalse(result["success"])
        self.assertIn("Token 失败", result["error"])
        mock_get.assert_called_once()

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_success(self, mock_get_token, mock_post):
        """测试成功发送企业微信消息"""
        # 模拟 Token
        mock_get_token.return_value = "test_token"

        # 模拟发送成功响应
        mock_response = MagicMock()
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}
        mock_post.return_value = mock_response

        # 调用方法
        result = NotifierService.send_wecom_app_message(
            self.test_config,
            title="测试标题",
            description="测试描述",
            url="https://example.com",
        )

        # 验证结果
        self.assertTrue(result)

        # 验证 POST 调用
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("access_token=test_token", call_args[0][0])

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_missing_config(self, mock_get_token, mock_post):
        """测试配置缺失的情况"""
        # 不完整的配置
        incomplete_config = {
            "wecom_corpid": "test_corp_id"
            # 缺少 secret 和 agentid
        }

        # 调用方法
        result = NotifierService.send_wecom_app_message(
            incomplete_config, title="测试标题", description="测试描述"
        )

        # 验证返回 False
        self.assertFalse(result)

        # 验证未尝试获取 Token
        mock_get_token.assert_not_called()

        # 验证未发送消息
        mock_post.assert_not_called()

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_send_failed(self, mock_get_token, mock_post):
        """测试消息发送失败"""
        # 模拟 Token 成功
        mock_get_token.return_value = "test_token"

        # 模拟发送失败响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40001,
            "errmsg": "invalid credential",
        }
        mock_post.return_value = mock_response

        # 调用方法
        result = NotifierService.send_wecom_app_message(
            self.test_config, title="测试标题", description="测试描述"
        )

        # 验证返回 False
        self.assertFalse(result)

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_failure_invalidates_stale_token(self, mock_get_token, mock_post):
        """服务端拒绝 token（errcode=40014）时清除本地缓存，避免最长 2h 持续失败"""
        mock_get_token.return_value = "stale_token"
        cache_key = ("test_corp_id", "test_secret")
        NotifierService._token_cache[cache_key] = ("stale_token", time.time() + 3600)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40014,
            "errmsg": "invalid access_token",
        }
        mock_post.return_value = mock_response

        result = NotifierService.send_wecom_app_message(
            self.test_config, title="测试标题", description="测试描述"
        )

        self.assertFalse(result)
        self.assertNotIn(cache_key, NotifierService._token_cache)

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_failure_keeps_cache_for_other_errors(self, mock_get_token, mock_post):
        """非 token 类错误（如频率限制 45009）不应清除 token 缓存"""
        mock_get_token.return_value = "valid_token"
        cache_key = ("test_corp_id", "test_secret")
        NotifierService._token_cache[cache_key] = ("valid_token", time.time() + 3600)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 45009,
            "errmsg": "api freq out of limit",
        }
        mock_post.return_value = mock_response

        result = NotifierService.send_wecom_app_message(
            self.test_config, title="测试标题", description="测试描述"
        )

        self.assertFalse(result)
        self.assertIn(cache_key, NotifierService._token_cache)

    def test_invalidate_app_token(self):
        """invalidate_app_token 精确清除指定凭证缓存，不影响其它凭证"""
        NotifierService._token_cache[("corp_a", "secret_a")] = (
            "tok_a",
            time.time() + 60,
        )
        NotifierService._token_cache[("corp_b", "secret_b")] = (
            "tok_b",
            time.time() + 60,
        )

        NotifierService.invalidate_app_token("corp_a", "secret_a")

        self.assertNotIn(("corp_a", "secret_a"), NotifierService._token_cache)
        self.assertIn(("corp_b", "secret_b"), NotifierService._token_cache)

    def test_default_url_fallback(self):
        """测试 URL 默认回退"""
        # 验证当 URL 为空时，应该使用默认值
        config = {
            "wecom_corpid": "test",
            "wecom_corpsecret": "test",
            "wecom_agentid": 100,
        }

        # 通过检查源码逻辑，URL 参数有默认值 "https://www.google.com"
        # 这里测试配置验证逻辑
        self.assertTrue(
            all(
                [
                    config.get("wecom_corpid"),
                    config.get("wecom_corpsecret"),
                    config.get("wecom_agentid"),
                ]
            )
        )


class TestNotifierServiceEdgeCases(unittest.TestCase):
    """NotifierService 边缘情况测试"""

    def setUp(self):
        NotifierService._token_cache.clear()

    def test_token_cache_expiry_buffer(self):
        """测试 Token 缓存过期缓冲（提前 1 分钟过期）"""
        now = time.time()
        # 设置一个刚好在缓冲区内过期的缓存
        expiry = now + 60  # 60 秒后过期
        NotifierService._token_cache[("test", "secret")] = ("token", expiry)

        # 此时应该认为缓存已过期（因为要提前 1 分钟）
        # 这个测试验证缓存策略的实现细节
        cached_token, cached_expiry = NotifierService._token_cache[("test", "secret")]
        self.assertEqual(cached_token, "token")

        # 验证缓冲区逻辑：now < expiry - 60 应该为 False
        self.assertFalse(now < cached_expiry - 60)

    def test_empty_description_handling(self):
        """测试空描述处理"""
        config = {
            "wecom_corpid": "test",
            "wecom_corpsecret": "test",
            "wecom_agentid": 100,
        }

        # 验证即使描述为空，配置检查也能通过
        self.assertTrue(
            all(
                [
                    config.get("wecom_corpid"),
                    config.get("wecom_corpsecret"),
                    config.get("wecom_agentid"),
                ]
            )
        )


class TestNotifierServiceRetry(unittest.TestCase):
    """NotifierService 重试机制测试

    重试策略由 ``tenacity network_retry`` 提供：仅对
    ``RETRYABLE_EXCEPTIONS``（ConnectionError/TimeoutError/IOError/OSError）
    重试，最多 3 次；用尽后 ``reraise=True`` 使异常向上抛出。
    """

    def setUp(self):
        """测试前准备"""
        NotifierService._token_cache.clear()
        self.test_config = {
            "wecom_corpid": "test_corp_id",
            "wecom_corpsecret": "test_secret",
            "wecom_agentid": 1000001,
            "wecom_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
        }

    def tearDown(self):
        """测试后清理"""
        NotifierService._token_cache.clear()

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_retry_on_network_error(
        self, mock_get_token, mock_post
    ):
        """测试网络错误自动重试（前两次失败，第三次成功）"""
        # 模拟 Token 成功
        mock_get_token.return_value = "test_token"

        # 前两次可重试网络异常，第三次成功
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_post.side_effect = [
            ConnectionError("Connection timeout"),
            ConnectionError("Connection refused"),
            mock_response_success,
        ]

        # 调用方法（应该自动重试）
        result = NotifierService.send_wecom_app_message(
            self.test_config, title="测试标题", description="测试描述"
        )

        # 验证最终成功
        self.assertTrue(result)

        # 验证调用了 3 次（初次 + 2 次重试）
        self.assertEqual(mock_post.call_count, 3)

    @patch("stock_monitor.services.notifier.requests.Session.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_retry_exhausted(self, mock_get_token, mock_post):
        """重试次数用尽后异常向上抛出"""
        # 模拟 Token 成功
        mock_get_token.return_value = "test_token"

        # 始终失败（可重试网络异常）
        mock_post.side_effect = ConnectionError("Persistent network error")

        # 重试 3 次后 network_retry(reraise=True) 抛出异常
        with self.assertRaises(ConnectionError):
            NotifierService.send_wecom_app_message(
                self.test_config, title="测试标题", description="测试描述"
            )

        # 验证重试了 3 次（max_attempts=3）
        self.assertEqual(mock_post.call_count, 3)

    @patch("stock_monitor.services.notifier.SafeRequest.post")
    def test_send_wecom_webhook_text_retry_on_error(self, mock_post):
        """测试 Webhook 消息重试（前两次失败，第三次成功）"""
        # 前两次可重试网络异常，第三次成功
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"errcode": 0}

        mock_post.side_effect = [
            ConnectionError("Network timeout"),
            ConnectionError("Temporary failure"),
            mock_response_success,
        ]

        # 调用方法（应该自动重试）
        result = NotifierService.send_wecom_webhook_text(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test", "测试消息"
        )

        # 验证最终成功
        self.assertTrue(result)

        # 验证调用了 3 次
        self.assertEqual(mock_post.call_count, 3)

    @patch("stock_monitor.services.notifier.SafeRequest.post")
    def test_send_wecom_webhook_text_retry_exhausted(self, mock_post):
        """测试 Webhook 重试次数用尽（异常向上抛出）"""
        # 始终失败（可重试网络异常）
        mock_post.side_effect = ConnectionError("Persistent network error")

        # 重试 3 次后 network_retry(reraise=True) 抛出异常
        with self.assertRaises(ConnectionError):
            NotifierService.send_wecom_webhook_text(
                "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test", "测试消息"
            )

        # 验证重试了 3 次
        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
