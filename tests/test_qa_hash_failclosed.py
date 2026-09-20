#!/usr/bin/env python
"""QA 独立验证（T04）：下载校验 fail-closed 与官方域名白名单双向验证。

- 拒绝向：无哈希 / 非官方域名哈希文件 / 计算异常 / 哈希不匹配 → 必须 False
- 放行向：官方域名 + 正确 64 位 hex → 必须 True（防"过度拒绝致功能不可用"）
- 真实发布包格式：``**SHA256**: `hash``` 的 body 能被解析
"""

import hashlib
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from stock_monitor.core.app_update.downloader import (
    UpdateDownloader,
    _is_official_url,
    _is_valid_sha256,
)

OFFICIAL_HASH_URL = "https://github.com/owner/repo/releases/download/v1.0.0/sha256.txt"


def _make_file(directory: str, name: str, content: bytes) -> str:
    path = os.path.join(directory, name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


class _HashResp:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class BaseHashTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="qa_hash_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestRejectDirection(BaseHashTest):
    """拒绝向（fail-closed）。"""

    def test_no_hash_anywhere_rejected(self) -> None:
        path = _make_file(self.tmpdir, "update.zip", b"payload")
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        result = UpdateDownloader()._verify_hash(path, assets, {"body": ""})
        self.assertFalse(result)

    def test_non_official_hash_domain_rejected(self) -> None:
        content = b"payload"
        path = _make_file(self.tmpdir, "update.zip", content)
        assets = [
            {
                "name": "sha256.txt",
                "browser_download_url": "https://evil.example.com/sha256.txt",
            }
        ]
        result = UpdateDownloader()._verify_hash(
            path, assets, {"body": f"SHA256: {_sha(content)}"}
        )
        self.assertFalse(result)

    def test_bad_hash_format_rejected(self) -> None:
        path = _make_file(self.tmpdir, "update.zip", b"payload")
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        # 非 64 位 hex
        result = UpdateDownloader()._verify_hash(path, assets, {"body": "SHA256: zzzz"})
        self.assertFalse(result)

    def test_calculation_oserror_rejected(self) -> None:
        missing = os.path.join(self.tmpdir, "does_not_exist.zip")
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        body = f"SHA256: {_sha(b'anything')}"
        result = UpdateDownloader()._verify_hash(missing, assets, {"body": body})
        self.assertFalse(result)

    def test_hash_mismatch_rejected(self) -> None:
        path = _make_file(self.tmpdir, "update.zip", b"tampered")
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        result = UpdateDownloader()._verify_hash(
            path, assets, {"body": f"SHA256: {_sha(b'original')}"}
        )
        self.assertFalse(result)


class TestAllowDirection(BaseHashTest):
    """放行向：可信来源 + 正确哈希必须放行。"""

    def test_official_hash_file_and_matching_zip_allowed(self) -> None:
        content = b"real-release-payload"
        path = _make_file(self.tmpdir, "update.zip", content)
        assets = [
            {"name": "sha256.txt", "browser_download_url": OFFICIAL_HASH_URL},
            {"name": "update.zip", "browser_download_url": "https://x/y.zip"},
        ]
        with patch(
            "stock_monitor.core.app_update.downloader.requests.get",
            return_value=_HashResp(_sha(content)),
        ):
            result = UpdateDownloader()._verify_hash(path, assets, {"body": ""})
        self.assertTrue(result)

    def test_release_body_markdown_format_allowed(self) -> None:
        """真实发布格式 ``**SHA256**: `hash``` 应能被解析放行。"""
        content = b"release-via-body"
        path = _make_file(self.tmpdir, "update.zip", content)
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        body = f"## Release\n\n**SHA256**: `{_sha(content)}`\n"
        result = UpdateDownloader()._verify_hash(path, assets, {"body": body})
        self.assertTrue(result)

    def test_body_lowercase_hash_allowed(self) -> None:
        content = b"lowercase-hash"
        path = _make_file(self.tmpdir, "update.zip", content)
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        body = f"SHA256: {_sha(content).lower()}"
        result = UpdateDownloader()._verify_hash(path, assets, {"body": body})
        self.assertTrue(result)


class TestOfficialUrlWhitelist(unittest.TestCase):
    """官方域名白名单：精确匹配 hostname，拒绝子串/伪装。"""

    def test_accepts_official_hosts(self) -> None:
        for url in (
            "https://github.com/o/r/releases/download/v1/sha256.txt",
            "https://api.github.com/repos/o/r",
            "https://objects.githubusercontent.com/x",
            "https://raw.githubusercontent.com/o/r/main/sha256.txt",
            "https://codeload.github.com/o/r/zip",
        ):
            self.assertTrue(_is_official_url(url), f"应放行: {url}")

    def test_rejects_lookalike_hosts(self) -> None:
        for url in (
            "https://github.com.evil.com/sha256.txt",
            "https://evilgithub.com/sha256.txt",
            "https://github.com.evil.com/x",
            "http://notgithub.com/x",
            "https://evil.com/github.com",
            "https://github.com@evil.com/x",  # userinfo 伪装
            "ftp://github.com/x",
            "",
        ):
            self.assertFalse(_is_official_url(url), f"应拒绝: {url}")

    def test_standard_ports_accepted(self) -> None:
        """未指定端口或显式 443 应放行。"""
        for url in (
            "https://github.com/o/r/sha256.txt",
            "https://github.com:443/o/r/sha256.txt",
        ):
            self.assertTrue(_is_official_url(url), f"应放行: {url}")

    def test_nonstandard_port_rejected(self) -> None:
        """非标准端口应拒绝：urlsplit().hostname 会剥离端口，必须显式校验端口。"""
        for url in (
            "https://github.com:444/x",
            "https://api.github.com:8443/x",
        ):
            self.assertFalse(_is_official_url(url), f"应拒绝: {url}")


class TestSha256Format(unittest.TestCase):
    def test_valid_and_invalid(self) -> None:
        self.assertTrue(_is_valid_sha256("a" * 64))
        self.assertTrue(_is_valid_sha256("A1" * 32))
        self.assertFalse(_is_valid_sha256("a" * 63))
        self.assertFalse(_is_valid_sha256("a" * 65))
        self.assertFalse(_is_valid_sha256("g" * 64))  # 非 hex
        self.assertFalse(_is_valid_sha256(""))


class TestRejectCleansFile(BaseHashTest):
    def test_reject_removes_downloaded_file(self) -> None:
        content = b"payload"
        path = _make_file(self.tmpdir, "update.zip", content)
        assets = [{"name": "update.zip", "browser_download_url": "https://x/y.zip"}]
        UpdateDownloader()._verify_hash(path, assets, {"body": ""})
        self.assertFalse(os.path.exists(path), "被拒绝的下载文件应被清理")


if __name__ == "__main__":
    unittest.main()
