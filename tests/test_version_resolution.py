"""版本解析回归：pyproject.toml 必须优先于过期的 installed metadata。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from stock_monitor import version as version_mod


class TestVersionResolution(unittest.TestCase):
    def test_pyproject_is_source_of_truth(self):
        """源码树存在 pyproject.toml 时，__version__ 必须与其一致。"""
        import tomllib

        root = Path(version_mod.__file__).resolve().parent.parent
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        expected = data["project"]["version"]
        self.assertEqual(version_mod._resolve_version(), expected)
        self.assertEqual(version_mod.__version__, expected)

    def test_pyproject_wins_over_stale_metadata(self):
        """过期 egg-info/dist-info 不得覆盖 pyproject 版本。"""
        with (
            patch.object(version_mod, "_find_pyproject_version", return_value="9.9.9"),
            patch.object(
                version_mod, "_installed_metadata_version", return_value="1.0.0"
            ),
        ):
            self.assertEqual(version_mod._resolve_version(), "9.9.9")

    def test_metadata_fallback_when_no_pyproject(self):
        """找不到 pyproject 时回退 installed metadata。"""
        with (
            patch.object(version_mod, "_find_pyproject_version", return_value=None),
            patch.object(
                version_mod, "_installed_metadata_version", return_value="2.3.4"
            ),
        ):
            self.assertEqual(version_mod._resolve_version(), "2.3.4")

    def test_dev_fallback(self):
        """两者皆无时返回 dev 占位。"""
        with (
            patch.object(version_mod, "_find_pyproject_version", return_value=None),
            patch.object(version_mod, "_installed_metadata_version", return_value=None),
        ):
            self.assertEqual(version_mod._resolve_version(), "0.0.0-dev")


if __name__ == "__main__":
    unittest.main()
