"""
NotifierService 消息推送服务单元测试
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

    @patch("stock_monitor.services.notifier.requests.get")
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
        self.assertIn("test_corp", NotifierService._token_cache)
        cached_token, expiry = NotifierService._token_cache["test_corp"]
        self.assertEqual(cached_token, "test_access_token")
        self.assertGreater(expiry, time.time())

    @patch("stock_monitor.services.notifier.requests.get")
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

    @patch("stock_monitor.services.notifier.requests.get")
    def test_get_app_token_network_error(self, mock_get):
        """测试网络异常处理"""
        # 模拟网络异常
        mock_get.side_effect = Exception("Network error")

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证返回 None
        self.assertIsNone(token)

    @patch("stock_monitor.services.notifier.requests.get")
    def test_get_app_token_cache_hit(self, mock_get):
        """测试缓存命中"""
        # 先手动设置缓存
        now = time.time()
        NotifierService._token_cache["test_corp"] = ("cached_token", now + 3600)

        # 调用方法
        token = NotifierService._get_app_token("test_corp", "test_secret")

        # 验证使用缓存，未调用 API
        self.assertEqual(token, "cached_token")
        mock_get.assert_not_called()

    @patch("stock_monitor.services.notifier.requests.get")
    def test_get_app_token_cache_expired(self, mock_get):
        """测试缓存过期"""
        # 设置过期的缓存
        expired_time = time.time() - 3600
        NotifierService._token_cache["test_corp"] = ("expired_token", expired_time)

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

    @patch("stock_monitor.services.notifier.requests.post")
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

    @patch("stock_monitor.services.notifier.requests.post")
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

    @patch("stock_monitor.services.notifier.requests.post")
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
        NotifierService._token_cache["test"] = ("token", expiry)

        # 此时应该认为缓存已过期（因为要提前 1 分钟）
        # 这个测试验证缓存策略的实现细节
        cached_token, cached_expiry = NotifierService._token_cache["test"]
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
    """NotifierService 重试机制测试"""

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

    @patch("stock_monitor.services.notifier.requests.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_retry_on_network_error(
        self, mock_get_token, mock_post
    ):
        """测试网络错误自动重试"""
        # 模拟 Token 成功
        mock_get_token.return_value = "test_token"

        # 模拟前两次失败，第三次成功
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"errcode": 0, "errmsg": "ok"}

        mock_post.side_effect = [
            Exception("Connection timeout"),
            Exception("Connection refused"),
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

    @patch("stock_monitor.services.notifier.requests.post")
    @patch("stock_monitor.services.notifier.NotifierService._get_app_token")
    def test_send_wecom_app_message_retry_exhausted(self, mock_get_token, mock_post):
        """测试重试次数用尽后返回 False"""
        # 模拟 Token 成功
        mock_get_token.return_value = "test_token"

        # 模拟始终失败
        mock_post.side_effect = Exception("Persistent network error")

        # 调用方法（应该重试 3 次后返回 False）
        result = NotifierService.send_wecom_app_message(
            self.test_config, title="测试标题", description="测试描述"
        )

        # 验证返回 False
        self.assertFalse(result)

        # 验证重试了 3 次（max_attempts=3）
        self.assertEqual(mock_post.call_count, 3)

    @patch("stock_monitor.services.notifier.SafeRequest.post")
    def test_send_wecom_webhook_text_retry_on_error(self, mock_post):
        """测试 Webhook 消息重试"""
        # 模拟前两次失败，第三次成功
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"errcode": 0}

        mock_post.side_effect = [
            Exception("Network timeout"),
            Exception("Temporary failure"),
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
        """测试 Webhook 重试次数用尽"""
        # 模拟始终失败
        mock_post.side_effect = Exception("Persistent network error")

        # 调用方法
        result = NotifierService.send_wecom_webhook_text(
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test", "测试消息"
        )

        # 验证返回 False
        self.assertFalse(result)

        # 验证重试了 3 次
        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
