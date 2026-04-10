import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from ..utils.logger import app_logger

APP_DIR_NAME = "stock_monitor"
CONFIG_DIR_NAME = ".stock_monitor"


def _get_legacy_repo_config_dir() -> Path:
    """返回旧版开发环境使用的仓库内配置目录。"""
    package_root = Path(__file__).resolve().parent.parent
    return package_root / CONFIG_DIR_NAME


def _get_user_data_root() -> Path:
    """返回当前用户的数据根目录。"""
    if sys.platform == "win32":
        base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base_dir:
            return Path(base_dir)
    return Path.home() / ".local" / "share"


def _get_user_config_dir() -> Path:
    """开发环境统一使用用户目录，避免污染仓库。"""
    return _get_user_data_root() / APP_DIR_NAME


def _migrate_legacy_repo_config_if_needed(target_dir: Path) -> None:
    """首次切换到用户目录时，迁移旧仓库内的配置和缓存。"""
    legacy_dir = _get_legacy_repo_config_dir()
    if legacy_dir.resolve() == target_dir.resolve():
        return

    if not legacy_dir.exists() or target_dir.exists():
        return

    try:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(legacy_dir, target_dir)
        app_logger.info(f"已迁移旧配置目录: {legacy_dir} -> {target_dir}")
    except Exception as e:
        app_logger.warning(f"迁移旧配置目录失败，将继续使用新目录: {e}")


def get_config_dir():
    """获取配置目录路径，区分开发环境和生产环境。"""
    if hasattr(sys, "_MEIPASS"):
        config_dir = Path(os.path.dirname(sys.executable)) / CONFIG_DIR_NAME
    else:
        config_dir = _get_user_config_dir()
        _migrate_legacy_repo_config_if_needed(config_dir)

    config_dir.mkdir(parents=True, exist_ok=True)
    app_logger.info(f"使用配置目录: {config_dir}")
    return str(config_dir)


CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class ConfigManager:
    """配置管理器，封装配置的加载和保存操作"""

    _instance = None

    def __new__(cls, config_path: str = CONFIG_PATH):
        """
        实现单例模式，确保全局只有一个配置管理器实例

        Args:
            config_path: 配置文件路径
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = CONFIG_PATH):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        if self._initialized:
            return

        self.config_path = config_path
        self._config: dict[str, Any] = {}
        self._load_config()
        self._initialized = True

    def _load_config(self) -> None:
        """加载配置文件，包含完整的错误处理和默认值"""
        try:
            if not os.path.exists(self.config_path):
                self._handle_missing_config_file()
                return

            with open(self.config_path, encoding="utf-8") as f:
                config: dict[str, Any] = json.load(f)

            # 确保必要的键存在
            self._ensure_required_keys_exist(config)
            self._config = config
        except json.JSONDecodeError:
            self._handle_corrupted_config_file("JSON解码错误")
        except PermissionError:
            self._handle_permission_error_config()
        except Exception as e:
            self._handle_unknown_error_config(e)

    def _handle_missing_config_file(self) -> None:
        """处理配置文件不存在的情况"""
        self._create_default_config()

    def _save_config(self) -> bool:
        """
        保存配置文件

        Returns:
            bool: 保存是否成功
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            app_logger.info("配置文件保存成功")
            return True
        except Exception as e:
            app_logger.error(f"保存配置文件时发生错误: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项的值

        Args:
            key: 配置项键名
            default: 默认值

        Returns:
            配置项的值或默认值
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        设置配置项的值

        Args:
            key: 配置项键名
            value: 配置项的值

        Returns:
            bool: 是否保存成功
        """
        self._config[key] = value
        return self._save_config()

    def _create_default_config(self) -> dict[str, Any]:
        """创建默认配置文件"""
        default_config = self._get_default_config()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        self._config = default_config
        return default_config

    def _get_default_config(self) -> dict[str, Any]:
        """获取默认配置"""
        return {
            "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
            "refresh_interval": 5,
            "github_token": "",
            "window_pos": [],
            "settings_dialog_pos": [],
            "quant_enabled": False,
            "quant_scan_interval": 60,
            "wecom_webhook": "",
            "push_mode": "webhook",
            "wecom_corpid": "",
            "wecom_corpsecret": "",
            "wecom_agentid": "",
            # 量化推送防抖动配置
            "quant_alert_cooldown": 1800,  # 基础冷却时间（秒），默认30分钟
            "quant_alert_score_threshold": 2,  # 评分变化阈值，超过此值才重新推送
            "quant_alert_merge_enabled": True,  # 是否启用信号合并推送
            "quant_max_workers": None,  # 量化扫描线程数（None=自动）
        }

    def _ensure_required_keys_exist(self, config: dict[str, Any]) -> None:
        """确保必要的键存在"""
        default_config = self._get_default_config()
        for key, default_value in default_config.items():
            if key not in config:
                config[key] = default_value

    def _handle_corrupted_config_file(self, error_type: str) -> dict[str, Any]:
        """处理损坏的配置文件"""
        # 如果配置文件损坏，备份原文件并创建新配置
        error_msg = f"配置文件损坏({error_type})，正在创建新的配置文件..."
        app_logger.error(error_msg)

        if os.path.exists(self.config_path):
            # 备份原文件
            backup_path = self.config_path + ".bak"
            shutil.copy2(self.config_path, backup_path)
            backup_msg = f"原配置文件已备份为: {backup_path}"
            app_logger.info(backup_msg)

        # 创建默认配置文件
        default_config = self._get_default_config()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        app_logger.info(f"默认配置文件已创建: {self.config_path}")
        self._config = default_config
        return default_config

    def _handle_permission_error_config(self) -> dict[str, Any]:
        """处理配置文件权限错误"""
        error_msg = "配置文件权限错误，请检查文件权限"
        app_logger.error(error_msg)
        default_config = self._get_default_config()
        self._config = default_config
        return default_config

    def _handle_unknown_error_config(self, e: Exception) -> dict[str, Any]:
        """处理未知错误"""
        app_logger.error(f"加载配置文件时发生未知错误: {e}")
        self._config = self._get_default_config()
        return self._config


def load_config() -> dict[str, Any]:
    """加载配置文件，包含完整的错误处理和默认值"""
    manager = ConfigManager()
    # 由于使用了单例模式，这里直接返回内部配置的副本
    return manager._config.copy()


def save_config(cfg: dict[str, Any]) -> bool:
    """
    保存配置文件

    Args:
        cfg: 配置字典

    Returns:
        bool: 保存是否成功
    """
    manager = ConfigManager()
    # 确保必要的键存在，避免外部传入不完整的配置
    manager._ensure_required_keys_exist(cfg)
    manager._config = cfg
    return manager._save_config()
