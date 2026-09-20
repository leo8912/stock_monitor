#!/usr/bin/env python
"""QA 独立验证（T01）：日志脱敏的幂等性与多形态覆盖。

覆盖：大小写、query-string、已脱敏串、同一行多 key、带引号值；
并验证 ``RedactionFilter`` 在真实 ``LogRecord`` 上的端到端行为。
另含对"前缀式敏感字段名"的**特征化测试**（记录当前行为与潜在缺口）。
"""

import io
import logging
import unittest

from stock_monitor.utils.logger import RedactionFilter, redact_sensitive


class TestRedactSensitive(unittest.TestCase):
    def _assert_redacted(self, raw: str, secret: str) -> str:
        out = redact_sensitive(raw)
        self.assertNotIn(secret, out, f"原始密文残留: {out!r}")
        self.assertIn("***", out, f"未出现脱敏标记: {out!r}")
        return out

    def test_lowercase_corpsecret(self) -> None:
        out = self._assert_redacted("corpsecret=abc123", "abc123")
        self.assertIn("corpsecret=***", out)

    def test_uppercase_corpsecret(self) -> None:
        out = self._assert_redacted("CORPSECRET=TopSecret", "TopSecret")
        self.assertIn("CORPSECRET=***", out)

    def test_query_string_form(self) -> None:
        out = self._assert_redacted("?key=xyz&x=1", "xyz")
        self.assertIn("x=1", out, "非敏感参数不应被误删")

    def test_already_redacted_is_idempotent(self) -> None:
        once = redact_sensitive("corpsecret=abc123")
        twice = redact_sensitive(once)
        self.assertEqual(once, twice)
        self.assertIn("corpsecret=***", twice)

    def test_multiple_keys_same_line(self) -> None:
        raw = "token=AAA password=BBB key=CCC"
        out = redact_sensitive(raw)
        for secret in ("AAA", "BBB", "CCC"):
            self.assertNotIn(secret, out)
        self.assertEqual(out.count("***"), 3)

    def test_webhook_url_redacted(self) -> None:
        self._assert_redacted(
            "webhook=https://open.feishu.cn/hook/verylongtoken", "verylongtoken"
        )

    def test_quoted_value(self) -> None:
        out = self._assert_redacted('secret: "s3cr3t!"', "s3cr3t!")
        self.assertEqual(out.count("***"), 1)

    def test_none_and_empty_passthrough(self) -> None:
        self.assertEqual(redact_sensitive(""), "")
        self.assertIsNone(redact_sensitive(None))

    def test_idempotent_across_all_variants(self) -> None:
        variants = [
            "corpsecret=abc123",
            "CORPSECRET=x",
            "?key=xyz&x=1",
            "corpsecret=***",
            "token=AAA password=BBB",
            'secret: "v"',
        ]
        for raw in variants:
            once = redact_sensitive(raw)
            self.assertEqual(
                redact_sensitive(once), once, f"非幂等: {raw!r} -> {once!r}"
            )

    def test_prefixed_field_names_are_redacted(self) -> None:
        """前缀式字段名（access_token/api_key/app_secret）必须脱敏。

        旧版用 `\\b` 裸词边界，导致带前缀的字段名漏脱；改为字段名模式后应命中。
        """
        for raw, secret in (
            ("access_token=ABCDEF", "ABCDEF"),
            ("api_key=K123456", "K123456"),
            ("app_secret=S98765", "S98765"),
        ):
            out = redact_sensitive(raw)
            self.assertNotIn(secret, out, f"密文残留: {raw!r} -> {out!r}")
            self.assertIn("***", out)

    def test_plain_english_words_not_redacted(self) -> None:
        """普通英文词（无 `=`/`:` 分隔符）不应被误脱敏。"""
        for raw in (
            "cache key 已更新",
            "secretary 提交了报告",
            "the token payload is ready",
        ):
            self.assertEqual(
                redact_sensitive(raw),
                raw,
                f"被误脱敏: {raw!r} -> {redact_sensitive(raw)!r}",
            )

    def test_false_positive_guards_extended(self) -> None:
        """A1 补漏后，误脱防护样例必须逐条保持原样（含新增 monkey/keychain）。"""
        for raw in (
            "cache key 已更新",
            "secretary 提交了申请",
            "the token payload is ready",
            "monkey patch",
            "keychain 访问",
        ):
            self.assertEqual(
                redact_sensitive(raw),
                raw,
                f"被误脱敏: {raw!r} -> {redact_sensitive(raw)!r}",
            )

    def test_authorization_and_cookie_headers_redacted(self) -> None:
        """Authorization / Cookie / sessionid 形态必须整体脱敏（含 scheme 前缀）。"""
        cases = (
            ("Authorization: Bearer xxxSECRET", "xxxSECRET"),
            ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
            ("authorization=Bearer tok123", "tok123"),
            ("Cookie: sessionid=abcdef123", "abcdef123"),
            ("sessionid=s3cr3tvalue", "s3cr3tvalue"),
        )
        for raw, secret in cases:
            out = self._assert_redacted(raw, secret)
            # scheme 词不应作为"值"残留（整体脱敏）
            self.assertNotIn(secret, out)
            # 幂等
            self.assertEqual(redact_sensitive(out), out, f"非幂等: {raw!r} -> {out!r}")

    def test_extra_credential_forms_redacted(self) -> None:
        """补充漏脱样例（空格分隔 / query / 驼峰 / 头名）必须被脱敏。"""
        cases = (
            ("app_secret = S98765", "S98765"),
            ("?access_token=AAA&x=1", "AAA"),
            ("X-Api-Key: K123456", "K123456"),
            ("accessToken=CAMEL123", "CAMEL123"),
            ("corpsecret=abc123", "abc123"),
        )
        for raw, secret in cases:
            self._assert_redacted(raw, secret)


class TestRedactionFilter(unittest.TestCase):
    def test_filter_redacts_record_and_clears_args(self) -> None:
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="token=%s",
            args=("SECRETVAL",),
            exc_info=None,
        )
        ok = RedactionFilter().filter(record)
        self.assertTrue(ok)
        rendered = record.getMessage()
        self.assertNotIn("SECRETVAL", rendered)
        self.assertEqual(record.args, ())

    def test_filter_passthrough_when_nothing_sensitive(self) -> None:
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="普通日志 123",
            args=(),
            exc_info=None,
        )
        self.assertTrue(RedactionFilter().filter(record))
        self.assertIn("普通日志 123", record.getMessage())


class TestRedactionEndToEnd(unittest.TestCase):
    def test_handler_output_is_redacted(self) -> None:
        logger = logging.getLogger("qa_redaction_e2e")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(RedactionFilter())
        logger.addHandler(handler)
        try:
            logger.info("webhook=https://x/hook/TOTALLY_SECRET_VALUE")
        finally:
            logger.removeHandler(handler)
        output = stream.getvalue()
        self.assertNotIn("TOTALLY_SECRET_VALUE", output)
        self.assertIn("***", output)


if __name__ == "__main__":
    unittest.main()
