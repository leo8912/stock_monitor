"""
消息推送服务层
负责将底层量化分析引擎捕捉到的高优信号，即时推送到指定的外部通信渠道（如企业微信机器人）
"""

import os
import threading
import time
from typing import Optional

import requests

from ..utils.logger import app_logger
from ..utils.network_helper import (
    APIResponseError,
    HTTPStatusError,
    NetworkRequestError,
    SafeRequest,
    TimeoutConfig,
)

# ====== 网络请求常量 ======
DEFAULT_TIMEOUT_SECONDS = 10  # 默认超时时间 (秒)
WEBHOOK_TIMEOUT_SECONDS = 5  # Webhook 超时时间 (秒)
TOKEN_EXPIRY_BUFFER_SECONDS = 60  # Token 提前过期缓冲 (秒)


# ====== 重试装饰器 ======
def retry(max_attempts: int = 3, backoff_factor: float = 0.5):
    """
    指数退避重试装饰器
    - max_attempts: 最大重试次数 (默认3次)
    - backoff_factor: 退避因子 (默认0.5秒)
      重试延迟: 0.5s, 1s, 2s, 4s...
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor * (2**attempt)
                        app_logger.warning(
                            f"[重试] {func.__name__} 失败 (第{attempt+1}次), "
                            f"{wait_time:.1f}秒后重试... 原因: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        app_logger.error(
                            f"[重试失败] {func.__name__} 已达最大重试次数({max_attempts}次), "
                            f"最后异常: {e}"
                        )
            # 全部重试失败，返回False
            return False

        return wrapper

    return decorator


class NotifierService:
    # 简单的应用 Token 缓存: {corp_id: (token, expiry_ts)}
    _token_cache = {}
    # 共享 HTTP 会话（连接池复用）
    _session = None
    _lock = threading.Lock()

    @classmethod
    def _get_session(cls):
        """获取共享的 requests.Session"""
        if cls._session is None:
            with cls._lock:
                if cls._session is None:
                    cls._session = requests.Session()
                    cls._session.headers.update({"Content-Type": "application/json"})
        return cls._session

    @classmethod
    def _get_app_token(cls, corp_id: str, secret: str) -> Optional[str]:
        """获取并快缓存企业微信应用 AccessToken"""
        import time

        now = time.time()

        # 1. 检查缓存
        with cls._lock:
            if corp_id in cls._token_cache:
                token, expiry = cls._token_cache[corp_id]
                if now < expiry - 60:  # 提前1分钟过期
                    return token

        # 2. 从服务器获取
        try:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corp_id}&corpsecret={secret}"
            resp = cls._get_session().get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                token = resp["access_token"]
                expires_in = resp.get("expires_in", 7200)
                with cls._lock:
                    cls._token_cache[corp_id] = (token, now + expires_in)
                return token
            else:
                app_logger.error(f"获取企微 App Token 失败: {resp}")
        except Exception as e:
            app_logger.error(f"获取企微 App Token 异常: {e}")
        return None

    @classmethod
    @retry(max_attempts=3, backoff_factor=0.5)
    def send_wecom_app_message(
        cls, config: dict, title: str, description: str, url: str = ""
    ) -> bool:
        """发送企业微信应用消息（使用 markdown 格式以获得更好的渲染效果）

        支持自动重试机制（指数退避）
        """
        corp_id = config.get("wecom_corpid")
        secret = config.get("wecom_corpsecret")
        agent_id = config.get("wecom_agentid")

        if not all([corp_id, secret, agent_id]):
            app_logger.warning("企微应用配置不全，无法发送卡片消息。")
            return False

        token = cls._get_app_token(corp_id, secret)
        if not token:
            return False

        send_url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        )

        # 【优化】使用 text 消息类型替代 markdown，以获得更好的个人微信兼容性
        payload = {
            "touser": "@all",
            "msgtype": "text",
            "agentid": agent_id,
            "text": {"content": f"{title}\n\n{description}"},
            "safe": 0,
        }

        try:
            resp = cls._get_session().post(send_url, json=payload, timeout=10).json()
            if resp.get("errcode") == 0:
                app_logger.info(f"企微应用消息发送成功: {title}")
                return True
            else:
                app_logger.error(f"企微应用消息发送失败: {resp}")
                return False
        except Exception as e:
            app_logger.error(f"企微应用消息推送异常: {e}")
            raise  # 让retry装饰器捕获异常

    @staticmethod
    @retry(max_attempts=3, backoff_factor=0.5)
    def send_wecom_webhook_text(webhook_url: str, content: str) -> bool:
        """向企业微信机器人的 Webhook 发送纯文本消息

        支持自动重试机制（指数退避）
        """
        if not webhook_url or not webhook_url.startswith("https://"):
            app_logger.warning(f"无效的 Webhook URL: {webhook_url}")
            return False

        headers = {"Content-Type": "application/json"}
        payload = {"msgtype": "text", "text": {"content": content}}

        try:
            resp = SafeRequest.post(
                webhook_url, json=payload, headers=headers, timeout=TimeoutConfig.SHORT
            )
            return resp.json().get("errcode") == 0

        except (HTTPStatusError, APIResponseError, NetworkRequestError) as e:
            app_logger.error(f"Webhook 消息推送失败：{e}")
            raise  # 让retry装饰器捕获异常
        except Exception as e:
            app_logger.error(f"Webhook 消息推送异常: {e}")
            raise  # 让retry装饰器捕获异常

    @classmethod
    def dispatch_alert(
        cls,
        config: dict,
        symbol: str,
        stock_name: str,
        signals: list[str],
        cycle_info: str = "",
        price_info: Optional[dict] = None,
    ) -> bool:
        """
        分发预警：优先使用企业应用通道，若未配置则回退到 Webhook 文字。
        【优化】使用 Markdown 格式替代 HTML，确保企业微信正确渲染
        """
        if not signals:
            return False

        # 【优化】优雅处理缺失的价格数据
        if price_info and price_info.get("price", 0) > 0:
            p = price_info.get("price", 0.0)
            pct = price_info.get("pct", 0.0)
            sign = "+" if pct >= 0 else ""
            price_display = f"{sign}{pct:.2f}%"
            price_detail = f"📊 **实时股价**: ¥{p:.2f} ({sign}{pct:.2f}%)"
        else:
            # 价格数据缺失时的降级显示
            price_display = "价格待更新"
            price_detail = "📊 **实时股价**: -- (数据获取中)"
            app_logger.debug(f"[推送降级] {symbol} 价格数据缺失，使用降级显示")

        title = f"🚨 异动: {stock_name} ({symbol}) {price_display}"

        # 【优化】使用纯文本格式以确保个人微信链接可点击
        signal_rows = "\n".join([f"• {s}" for s in signals])
        desc_body = (
            f"{price_detail}\n\n"
            f"关键信号：\n"
            f"{signal_rows}\n\n"
            f"---\n\n"
            f"{cycle_info}"
        )

        success = False
        # 1. 尝试企业应用（改用 text 格式以兼容个人微信）
        if config.get("push_mode") == "app" or config.get("wecom_corpsecret"):
            agent_id = config.get("wecom_agentid", "")
            corp_id = config.get("wecom_corpid", "")
            corp_secret = config.get("wecom_corpsecret", "")

            if all([agent_id, corp_id, corp_secret]):
                # 获取 Access Token（使用缓存）
                try:
                    access_token = cls._get_app_token(corp_id, corp_secret)
                    if access_token:
                        send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

                        # 构造纯文本内容
                        full_content = f"{title}\n\n{desc_body}"
                        payload = {
                            "touser": "@all",
                            "msgtype": "text",
                            "agentid": int(agent_id)
                            if str(agent_id).isdigit()
                            else agent_id,
                            "text": {"content": full_content},
                            "safe": 0,
                        }
                        resp = (
                            cls._get_session()
                            .post(send_url, json=payload, timeout=10)
                            .json()
                        )
                        if resp.get("errcode") == 0:
                            app_logger.info(f"企微应用消息发送成功: {title}")
                            success = True
                        else:
                            app_logger.error(f"企微应用消息发送失败: {resp}")
                    else:
                        app_logger.error(
                            f"获取企微 Token 失败: access_token={access_token}"
                        )
                except Exception as e:
                    app_logger.error(f"企微应用消息推送异常: {e}")
            else:
                app_logger.warning("企微应用配置不完整，跳过应用通道推送")

        # 2. 回退到 Webhook（纯文本）
        if not success:
            webhook_url = config.get("wecom_webhook", "")
            if webhook_url:
                app_logger.info(
                    "企微应用推送未成功（可能是IP白名单限制），正在回退至 Webhook 渠道推送预警..."
                )
                body = f"{title}\n\n{price_detail}\n\n**关键信号：**\n{signal_rows}\n\n---\n\n{cycle_info}"
                return cls.send_wecom_webhook_text(webhook_url, body)
            else:
                app_logger.warning(
                    "企微应用推送失败，且未配置 Webhook URL，无法发送预警"
                )
                return False
        return True

    @classmethod
    def dispatch_report(
        cls, config: dict, title: str, content_items: list[str], footer: str = ""
    ) -> bool:
        """推送汇总型报告（使用 markdown 格式）"""
        if not content_items:
            return False

        # 1. 企业应用通道 (每一个股一条 markdown 信息，防止信息过长被隐藏)
        success = False
        if config.get("push_mode") == "app" or config.get("wecom_corpsecret"):
            try:
                # 发送概览总卡片
                header_desc = (
                    f"{footer}\n\n**报告时间**: {time.strftime('%Y-%m-%d %H:%M')}"
                )
                if cls.send_wecom_app_message(
                    config, f"📊 {title} (总览)", header_desc
                ):
                    success = True
                    # 循环发送每一个股详情卡片
                    for item in content_items:
                        card_title = "个股表现"
                        first_line = item.split("\n")[0]
                        if "**" in first_line:
                            card_title = first_line.replace("**", "").strip()

                        card_desc = (
                            "\n".join(item.split("\n")[1:]) if "\n" in item else item
                        )
                        cls.send_wecom_app_message(
                            config, f"📈 {card_title}", card_desc
                        )
                        time.sleep(0.5)
            except Exception as app_err:
                app_logger.error(f"企业应用推送汇总报告异常: {app_err}")
                success = False

        # App 通道成功，直接返回
        if success:
            return True

        # 2. Webhook Markdown 通道
        if not success:
            webhook_url = config.get("wecom_webhook", "")
            if not webhook_url:
                app_logger.warning(
                    "企微应用发送未成功且未配置 Webhook URL，无法发送汇总报告"
                )
                return False

            app_logger.info(
                "企微应用发送未成功（可能是IP白名单限制），正在回退至 Webhook 渠道推送汇总报告..."
            )
            text_content = (
                f"📊 {title}\n\n报告时间：{time.strftime('%Y-%m-%d %H:%M')}\n\n"
            )
            text_content += "\n\n".join(
                [item.replace("**", "") for item in content_items]
            )
            if footer:
                text_content += f"\n\n---\n{footer}"
            return cls.send_wecom_webhook_text(webhook_url, text_content)

    @classmethod
    def dispatch_custom_message(
        cls,
        config: dict,
        title: str,
        content: str,
        webhook_override: Optional[str] = None,
    ) -> bool:
        """
        发送自定义消息（用于定时复盘报告，使用 markdown 格式）

        Args:
            config: 配置字典
            title: 消息标题
            content: 消息内容（markdown 格式）
            webhook_override: 可选的 Webhook URL 覆盖

        Returns:
            bool: 是否发送成功
        """
        try:
            # 1. 企业应用通道
            success = False
            if config.get("push_mode") == "app" or config.get("wecom_corpsecret"):
                try:
                    success = cls.send_wecom_app_message(config, title, content)
                except Exception as app_err:
                    app_logger.error(f"企业应用推送异常: {app_err}")
                    success = False

            # 2. Webhook Markdown 通道
            if not success:
                webhook_url = webhook_override or config.get("wecom_webhook", "")
                if not webhook_url:
                    app_logger.warning(
                        "企微应用发送未成功且未配置 Webhook URL，无法发送自定义消息"
                    )
                    return False

            # 如果内容包含 HTML 标签或 Markdown 符号，尝试进行简单的清理转换为纯文本
            import re

            text_content = content
            if "<" in text_content and ">" in text_content:
                text_content = re.sub(r"<[^>]+>", "", text_content)  # 移除 HTML 标签
                text_content = text_content.replace("&nbsp;", " ").strip()

            # 移除常见的 Markdown 标记
            text_content = text_content.replace("**", "")
            text_content = re.sub(r"^#+\s+", "", text_content, flags=re.MULTILINE)

            return cls.send_wecom_webhook_text(
                webhook_url, f"【{title}】\n\n{text_content}"
            )
        except Exception as e:
            app_logger.error(f"发送自定义消息失败：{e}")
            return False

    @classmethod
    def dispatch_image(
        cls,
        config: dict,
        image_path: str,
        title: str = "",
    ) -> bool:
        """
        推送图片消息（支持企业应用通道与 Webhook 通道）

        Args:
            config: 配置字典
            image_path: 本地图片路径
            title: 辅助标题文本（发送完图片后会以文本消息形式追加发送，作为说明）

        Returns:
            bool: 是否发送成功
        """
        if not image_path or not os.path.exists(image_path):
            app_logger.warning(f"图片路径无效或不存在: {image_path}")
            return False

        try:
            # 1. 企业微信应用通道 (App)
            success = False
            if config.get("push_mode") == "app" or config.get("wecom_corpsecret"):
                corp_id = config.get("wecom_corpid", "")
                corp_secret = config.get("wecom_corpsecret", "")
                agent_id = config.get("wecom_agentid", "")

                if all([corp_id, corp_secret, agent_id]):
                    token = cls._get_app_token(corp_id, corp_secret)
                    if token:
                        # A. 上传临时素材获取 media_id
                        upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"
                        try:
                            with open(image_path, "rb") as f:
                                files = {"media": f}
                                upload_resp = (
                                    cls._get_session()
                                    .post(upload_url, files=files, timeout=15)
                                    .json()
                                )

                            media_id = upload_resp.get("media_id")
                            if media_id:
                                # B. 发送图片消息
                                send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
                                payload = {
                                    "touser": "@all",
                                    "msgtype": "image",
                                    "agentid": int(agent_id)
                                    if str(agent_id).isdigit()
                                    else agent_id,
                                    "image": {"media_id": media_id},
                                    "safe": 0,
                                }
                                resp = (
                                    cls._get_session()
                                    .post(send_url, json=payload, timeout=10)
                                    .json()
                                )
                                if resp.get("errcode") == 0:
                                    app_logger.info("企微应用图片消息发送成功")
                                    if title:
                                        # 追加一条说明文本
                                        cls.send_wecom_app_message(
                                            config, "说明", title
                                        )
                                    success = True
                                else:
                                    app_logger.error(f"企微应用图片发送失败: {resp}")
                            else:
                                app_logger.error(
                                    f"企微图片上传失败，响应: {upload_resp}"
                                )
                        except Exception as upload_err:
                            app_logger.error(
                                f"企微图片上传/发送过程发生异常: {upload_err}"
                            )
                    else:
                        app_logger.error("获取企微 Token 失败，跳过应用通道图片发送")
                else:
                    app_logger.warning("企微应用配置不全，跳过图片应用通道。")

            # 2. Webhook 通道 (图片 Base64 + MD5)
            if not success:
                webhook_url = config.get("wecom_webhook", "")
                if not webhook_url:
                    app_logger.warning("未配置 Webhook URL，无法发送图片消息")
                    return False

                import base64
                import hashlib

                # 读取图片字节，计算 MD5 和 Base64
                with open(image_path, "rb") as f:
                    image_bytes = f.read()
                    md5_str = hashlib.md5(image_bytes).hexdigest()
                    base64_str = base64.b64encode(image_bytes).decode("utf-8")

                payload = {
                    "msgtype": "image",
                    "image": {"base64": base64_str, "md5": md5_str},
                }

                headers = {"Content-Type": "application/json"}
                resp = (
                    cls._get_session()
                    .post(webhook_url, json=payload, headers=headers, timeout=15)
                    .json()
                )

                if resp.get("errcode") == 0:
                    app_logger.info("Webhook 图片发送成功")
                    if title:
                        # 追加一条说明文本
                        cls.send_wecom_webhook_text(webhook_url, title)
                    return True
                else:
                    app_logger.error(f"Webhook 图片发送失败: {resp}")
                    return False
            return True

        except Exception as e:
            app_logger.error(f"发送图片消息异常: {e}", exc_info=True)
            return False
