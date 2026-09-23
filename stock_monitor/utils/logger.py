import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler

# 敏感字段脱敏正则集合（大小写不敏感）。
#
# 设计要点（同时修「漏脱」与「误脱」）：
#   1) 以「字段名」为单位匹配，而非裸词。字段名允许任意前缀/后缀，从而覆盖
#      access_token / api_key / app_secret / corpsecret / authorization / cookie /
#      sessionid 等常见命名（旧版用 \b 裸词边界，导致带前缀的字段漏脱）。
#   2) 分隔符**必须包含 `=` 或 `:`**（赋值 / query-string 形态）。这一约束同时
#      消除了普通英文误脱：`cache key 已更新`、`secretary 提交` 这类空格分隔的
#      自然语言不会命中，而 `key=xxx` / `secret: "xxx"` 仍会被脱敏。
#   3) 裸 `key` 单独一条规则（`\bkey\b`，禁止前后缀），避免 monkey/keychain 等误伤。
#   4) 值前允许可选的 HTTP 认证 scheme 前缀（`Bearer`/`Basic`/`Digest` + 空格），
#      使 `Authorization: Bearer xxx` 整体被脱敏，而不是只吃掉 scheme 一词、留下凭据。
# 替换结果为 ***，因此对同一字符串重复执行是幂等的。
_SENSITIVE_VALUE_PATTERNS = (
    # 含敏感词的字段名（允许前后缀），分隔符须含 `=`/`:`/query 形态
    re.compile(
        r"(?i)([A-Za-z0-9_-]*"
        r"(?:corpsecret|secret|token|password|webhook|api[_-]?key|access[_-]?key"
        r"|authorization|cookie|sessionid)"
        r"[A-Za-z0-9_-]*)"
        r'(["\'\s]*[:=]["\'\s:=&]*)'
        r'((?:(?:Bearer|Basic|Digest) )?[^"\'\s,&]+)'
    ),
    # 裸 key：需处于赋值 / query-string 上下文（分隔符含 `=`/`:`）
    re.compile(r'(?i)\b(key)\b(["\'\s]*[:=]["\'\s:=&]*)([^"\'\s,&]+)'),
)


def redact_sensitive(message: str) -> str:
    """对日志消息中的敏感字段值进行脱敏。

    Args:
        message: 原始日志消息。

    Returns:
        脱敏后的消息；对已脱敏内容重复调用结果不变（幂等）。
    """
    if not message:
        return message
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        message = pattern.sub(r"\1\2***", message)
    return message


class RedactionFilter(logging.Filter):
    """日志脱敏过滤器。

    在日志记录真正被 handler 渲染前，将消息中的敏感字段值替换为 ***，
    随后清空 ``record.args``，避免格式化阶段重新拼接原始参数。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤回调：就地脱敏 ``record``，始终返回 True 以放行日志。"""
        try:
            message = record.getMessage()
        except Exception:
            # 消息格式化本身失败时不阻断日志，交由 handler 处理
            logging.getLogger(__name__).debug(
                "日志消息格式化失败，跳过脱敏", exc_info=True
            )
            return True

        redacted = redact_sensitive(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class Logger:
    """日志记录器（支持结构化字段）"""

    def __init__(
        self,
        name: str = "stock_monitor",
        log_file: str | None = None,
        log_level: int = logging.INFO,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        file_level: int = logging.INFO,
    ) -> None:
        """
        初始化日志记录器

        Args:
            name: 日志记录器名称
            log_file: 日志文件路径，如果为None则只输出到控制台
            log_level: 日志级别
            max_file_size: 单个日志文件最大大小（字节）
            backup_count: 保留的备份日志文件数量
            file_level: 文件处理器日志级别（默认 INFO）
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        # 清除现有的处理器以避免重复：先关闭旧 handler 释放文件句柄，
        # 防止重复初始化时句柄泄漏。
        for handler in list(self.logger.handlers):
            try:
                handler.close()
            except Exception:
                # 关闭旧 handler 失败不应阻断新 handler 注册。此刻 Logger
                # 尚未就绪，使用标准 logging 兜底以避免依赖 app_logger。
                logging.getLogger(__name__).debug(
                    "关闭旧日志 handler 失败", exc_info=True
                )
        self.logger.handlers.clear()

        # 敏感信息脱敏过滤器（console 与 file 均需挂载）
        redaction_filter = RedactionFilter()

        # 创建格式化器（文件日志包含结构化字段）
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
        )

        # 添加控制台处理器
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s"
        )
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(redaction_filter)
        self.logger.addHandler(console_handler)

        # 如果指定了日志文件，添加文件处理器（带轮转）
        if log_file:
            # 确保日志目录存在
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # 使用轮转文件处理器
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(file_level)  # 文件处理器级别可配置，默认 INFO
            file_handler.setFormatter(formatter)
            file_handler.addFilter(redaction_filter)
            self.logger.addHandler(file_handler)

    def debug(self, message: str, *args, **kwargs) -> None:
        """记录调试信息"""
        kwargs["stacklevel"] = 2
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """记录一般信息"""
        kwargs["stacklevel"] = 2
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """记录警告信息"""
        kwargs["stacklevel"] = 2
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """记录错误信息"""
        kwargs["stacklevel"] = 2
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """记录严重错误信息"""
        kwargs["stacklevel"] = 2
        self.logger.critical(message, *args, **kwargs)

    # ── 结构化日志方法 ──────────────────────────────────────────────

    def log_with_context(
        self,
        level: int,
        message: str,
        **context,
    ) -> None:
        """
        带结构化上下文的日志记录

        Args:
            level: 日志级别
            message: 日志消息
            **context: 结构化字段（symbol, action, duration_ms 等）
        """
        if context:
            ctx_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} [{ctx_str}]"
        else:
            full_message = message
        self.logger.log(level, full_message, stacklevel=3)

    def info_ctx(self, message: str, **context) -> None:
        """以 INFO 级别记录带结构化上下文的日志。"""
        self.log_with_context(logging.INFO, message, **context)

    def warning_ctx(self, message: str, **context) -> None:
        """以 WARNING 级别记录带结构化上下文的日志。"""
        self.log_with_context(logging.WARNING, message, **context)

    def error_ctx(self, message: str, **context) -> None:
        """以 ERROR 级别记录带结构化上下文的日志。"""
        self.log_with_context(logging.ERROR, message, **context)


def setup_logger(name: str = "stock_monitor", log_level: int = logging.INFO) -> Logger:
    """
    设置并返回日志记录器实例

    Args:
        name: 日志记录器名称
        log_level: 日志级别

    Returns:
        Logger实例
    """
    try:
        # 获取项目根目录或可执行文件目录
        if getattr(sys, "frozen", False):
            # PyInstaller打包环境
            project_root = os.path.dirname(sys.executable)
        else:
            # 源码运行环境
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 创建日志目录
        log_dir = os.path.join(project_root, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 日志文件路径
        log_file_path = os.path.join(log_dir, "stock_monitor.log")

        # 创建日志记录器
        return Logger(name, log_file_path, log_level)
    except Exception:
        # 如果创建文件日志失败，则只使用控制台日志
        return Logger(name, log_level=log_level)


# 创建全局日志记录器实例
app_logger = setup_logger()
