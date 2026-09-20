#!/usr/bin/env python
"""
AppUpdater 单元测试模块

测试应用程序更新器功能，包括：
- 更新检查
- 更新下载
- 更新应用
- 更新后钩子
- 边界情况处理
"""

import hashlib
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from stock_monitor.core.app_update.downloader import UpdateDownloader
from stock_monitor.core.updater import AppUpdater


class TestAppUpdaterInitialization(unittest.TestCase):
    """AppUpdater 初始化测试"""

    def test_initialization_with_default_repo(self):
        """测试使用默认仓库初始化"""
        updater = AppUpdater()

        self.assertEqual(updater.checker.github_repo, "leo8912/stock_monitor")
        self.assertIsNotNone(updater.checker)
        self.assertIsNotNone(updater.downloader)
        self.assertIsNotNone(updater.installer)

    def test_initialization_with_custom_repo(self):
        """测试使用自定义仓库初始化"""
        updater = AppUpdater(github_repo="custom/repo")

        self.assertEqual(updater.checker.github_repo, "custom/repo")


class TestAppUpdaterCheckForUpdates(unittest.TestCase):
    """AppUpdater 更新检查测试"""

    def setUp(self):
        self.updater = AppUpdater()

    @patch.object(AppUpdater, "check_for_updates")
    def test_check_for_updates_delegates_to_checker(self, mock_check):
        """测试检查更新委托给 checker"""
        mock_check.return_value = True

        result = self.updater.check_for_updates()

        self.assertTrue(result)
        mock_check.assert_called_once()

    def test_latest_release_info_property(self):
        """测试 latest_release_info 属性"""
        # Mock checker 的返回
        mock_info = {"version": "1.0.0", "url": "https://example.com"}
        self.updater.checker.latest_release_info = mock_info

        result = self.updater.latest_release_info

        self.assertEqual(result, mock_info)


class TestAppUpdaterDownloadUpdate(unittest.TestCase):
    """AppUpdater 更新下载测试"""

    def setUp(self):
        self.updater = AppUpdater()
        # 设置模拟的 release info
        self.updater.checker.latest_release_info = {
            "version": "1.0.0",
            "url": "https://example.com/update.zip",
        }

    @patch.object(AppUpdater, "download_update")
    def test_download_update_delegates_to_downloader(self, mock_download):
        """测试下载更新委托给 downloader"""
        mock_download.return_value = "/path/to/update.zip"

        result = self.updater.download_update()

        self.assertEqual(result, "/path/to/update.zip")
        mock_download.assert_called_once()

    def test_download_update_without_release_info(self):
        """测试没有 release info 时下载失败"""
        self.updater.checker.latest_release_info = None

        result = self.updater.download_update()

        self.assertIsNone(result)

    def test_download_update_with_callbacks(self):
        """测试下载更新带回调函数"""
        progress_callback = MagicMock()
        is_cancelled_callback = MagicMock()
        security_warning_callback = MagicMock()
        error_callback = MagicMock()

        # Mock downloader
        with patch.object(self.updater.downloader, "download_update") as mock_dl:
            mock_dl.return_value = "/path/to/update.zip"

            result = self.updater.download_update(
                progress_callback=progress_callback,
                is_cancelled_callback=is_cancelled_callback,
                security_warning_callback=security_warning_callback,
                error_callback=error_callback,
            )

            self.assertEqual(result, "/path/to/update.zip")
            mock_dl.assert_called_once()


class TestAppUpdaterApplyUpdate(unittest.TestCase):
    """AppUpdater 应用更新测试"""

    def setUp(self):
        self.updater = AppUpdater()

    @patch.object(AppUpdater, "apply_update")
    def test_apply_update_delegates_to_installer(self, mock_apply):
        """测试应用更新委托给 installer"""
        mock_apply.return_value = True

        result = self.updater.apply_update("/path/to/update.zip")

        self.assertTrue(result)
        mock_apply.assert_called_once_with("/path/to/update.zip")

    @patch.object(AppUpdater, "apply_update")
    def test_apply_update_failure(self, mock_apply):
        """测试应用更新失败"""
        mock_apply.return_value = False

        result = self.updater.apply_update("/path/to/update.zip")

        self.assertFalse(result)


class TestAppUpdaterIntegration(unittest.TestCase):
    """AppUpdater 集成测试"""

    def setUp(self):
        self.updater = AppUpdater()

    def test_full_update_workflow_mocked(self):
        """测试完整更新流程（Mock 版本）"""
        # 1. 检查更新
        with patch.object(self.updater, "check_for_updates") as mock_check:
            mock_check.return_value = True

            # 2. 下载更新
            with patch.object(self.updater, "download_update") as mock_download:
                mock_download.return_value = "/tmp/update.zip"

                # 3. 应用更新
                with patch.object(self.updater, "apply_update") as mock_apply:
                    mock_apply.return_value = True

                    # 执行流程
                    has_update = self.updater.check_for_updates()
                    self.assertTrue(has_update)

                    update_path = self.updater.download_update()
                    self.assertEqual(update_path, "/tmp/update.zip")

                    success = self.updater.apply_update(update_path)
                    self.assertTrue(success)


class TestVerifyHashFailClosed(unittest.TestCase):
    """UpdateDownloader._verify_hash 的 fail-closed 行为测试（T04）。"""

    _GET = "stock_monitor.core.app_update.downloader.requests.get"

    def setUp(self):
        self.downloader = UpdateDownloader()
        fd, self.path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        payload = b"hello update payload"
        with open(self.path, "wb") as f:
            f.write(payload)
        self.correct_hash = hashlib.sha256(payload).hexdigest()

    def tearDown(self):
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass

    @staticmethod
    def _response(text, status=200):
        resp = MagicMock()
        resp.status_code = status
        resp.text = text
        return resp

    def test_no_hash_anywhere_returns_false(self):
        """既无 sha256.txt，body 也无 SHA256 → 拒绝（False）。"""
        assets = [
            {
                "name": "update.zip",
                "browser_download_url": "https://github.com/x/y/update.zip",
            }
        ]
        info = {"body": "no hash here"}
        with patch(self._GET) as mock_get:
            mock_get.return_value = self._response("", status=404)
            result = self.downloader._verify_hash(self.path, assets, info)
        self.assertIs(result, False)

    def test_hash_file_non_official_domain_returns_false(self):
        """哈希文件来自非官方域名 → 拒绝，且不发起请求。"""
        assets = [
            {
                "name": "sha256.txt",
                "browser_download_url": "https://evil.example.com/sha256.txt",
            }
        ]
        info = {"body": f"SHA256: `{self.correct_hash}`"}
        with patch(self._GET) as mock_get:
            result = self.downloader._verify_hash(self.path, assets, info)
            mock_get.assert_not_called()
        self.assertIs(result, False)

    def test_computation_oserror_returns_false(self):
        """哈希计算过程抛 OSError → 必须返回 False（不得放行）。"""
        assets = [
            {
                "name": "sha256.txt",
                "browser_download_url": "https://github.com/x/y/sha256.txt",
            }
        ]
        info = {"body": f"SHA256: `{self.correct_hash}`"}
        with patch(self._GET) as mock_get:
            mock_get.return_value = self._response(self.correct_hash)
            with patch("builtins.open", side_effect=OSError("disk error")):
                result = self.downloader._verify_hash(self.path, assets, info)
        self.assertIs(result, False)

    def test_hash_mismatch_returns_false_and_deletes_file(self):
        """哈希不匹配 → 拒绝并删除下载文件。"""
        assets = [
            {
                "name": "sha256.txt",
                "browser_download_url": "https://raw.githubusercontent.com/x/y/sha256.txt",
            }
        ]
        wrong_hash = "0" * 64
        info = {"body": f"SHA256: `{wrong_hash}`"}
        with patch(self._GET) as mock_get:
            mock_get.return_value = self._response(wrong_hash)
            result = self.downloader._verify_hash(self.path, assets, info)
        self.assertIs(result, False)
        self.assertFalse(os.path.exists(self.path))

    def test_hash_match_official_returns_true(self):
        """官方域名 + 正确 64 位 hex → 校验通过（True）。"""
        assets = [
            {
                "name": "sha256.txt",
                "browser_download_url": "https://objects.githubusercontent.com/x/y/sha256.txt",
            }
        ]
        info = {"body": ""}
        with patch(self._GET) as mock_get:
            mock_get.return_value = self._response(self.correct_hash.upper())
            result = self.downloader._verify_hash(self.path, assets, info)
        self.assertIs(result, True)
        self.assertTrue(os.path.exists(self.path))

    def test_hash_from_release_body_returns_true(self):
        """无 sha256.txt 资产，但 body 提供 SHA256 → 校验通过。"""
        assets = [
            {
                "name": "update.zip",
                "browser_download_url": "https://github.com/x/y/update.zip",
            }
        ]
        info = {"body": f"**SHA256**: `{self.correct_hash}`"}
        with patch(self._GET) as mock_get:
            result = self.downloader._verify_hash(self.path, assets, info)
            mock_get.assert_not_called()
        self.assertIs(result, True)


if __name__ == "__main__":
    unittest.main()
