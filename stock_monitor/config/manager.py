import os
import json
import shutil
import sys
from typing import Dict, Any, Optional, Union, List
from ..utils.logger import app_logger
from ..utils.helpers import handle_exception

# 配置文件路径 - 存在用户目录中，避免更新时丢失
# 简化配置路径处理逻辑，统一使用.stock_monitor目录
def get_config_dir():
    """获取配置目录路径，区分开发环境和生产环境"""
    # PyInstaller环境使用可执行文件所在目录，其他环境使用main.py所在目录
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller打包环境 - 使用可执行文件所在目录
        config_dir = os.path.join(os.path.dirname(sys.executable), '.stock_monitor')
    else:
        # 普通环境 - 使用main.py所在目录
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(current_dir, '.stock_monitor')
    
    app_logger.info(f"使用配置目录: {config_dir}")
    
    # 确保配置目录存在
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

CONFIG_DIR = get_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')


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
            cls._instance = super(ConfigManager, cls).__new__(cls)
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
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._initialized = True
    
    def _load_config(self) -> None:
        """加载配置文件，包含完整的错误处理和默认值"""
        def _load_config_impl():
            if not os.path.exists(self.config_path):
                # 创建默认配置文件
                default_config = {
                    "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                    "refresh_interval": 5,
                    "github_token": "",
                    "window_pos": [],
                    "settings_dialog_pos": []
                }
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                self._config = default_config
                return default_config
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config: Dict[str, Any] = json.load(f)
                
            # 确保必要的键存在
            if 'user_stocks' not in config:
                config['user_stocks'] = ["sh600460", "sh603986", "sh600030", "sh000001"]
            if 'refresh_interval' not in config:
                config['refresh_interval'] = 5
            if 'github_token' not in config:
                config['github_token'] = ""
            if 'window_pos' not in config:
                config['window_pos'] = []
            if 'settings_dialog_pos' not in config:
                config['settings_dialog_pos'] = []
                
            self._config = config
            return config
        
        def _handle_json_decode_error():
            # 如果JSON解析失败，备份原文件并创建新配置
            error_msg = f"配置文件损坏，正在创建新的配置文件..."
            app_logger.error(error_msg)
            print(error_msg)
            
            if os.path.exists(self.config_path):
                # 备份原文件
                backup_path = self.config_path + ".bak"
                shutil.copy2(self.config_path, backup_path)
                backup_msg = f"原配置文件已备份为: {backup_path}"
                app_logger.info(backup_msg)
                print(backup_msg)
                
            # 创建默认配置文件
            default_config = {
                "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                "refresh_interval": 5,
                "github_token": "",
                "window_pos": [],
                "settings_dialog_pos": []
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            app_logger.info(f"默认配置文件已创建: {self.config_path}")
            self._config = default_config
            return default_config
        
        def _handle_permission_error():
            error_msg = "配置文件权限错误，请检查文件权限"
            app_logger.error(error_msg)
            print(error_msg)
            default_config = {
                "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                "refresh_interval": 5,
                "github_token": "",
                "window_pos": [],
                "settings_dialog_pos": []
            }
            self._config = default_config
            return default_config
        
        try:
            _load_config_impl()
        except json.JSONDecodeError:
            handle_exception(
                "处理JSON解码错误",
                _handle_json_decode_error,
                {
                    "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                    "refresh_interval": 5,
                    "github_token": "",
                    "window_pos": [],
                    "settings_dialog_pos": []
                },
                app_logger
            )
        except PermissionError:
            handle_exception(
                "处理权限错误",
                _handle_permission_error,
                {
                    "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                    "refresh_interval": 5,
                    "github_token": "",
                    "window_pos": [],
                    "settings_dialog_pos": []
                },
                app_logger
            )
        except Exception:
            handle_exception(
                "加载配置文件",
                _load_config_impl,
                {
                    "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                    "refresh_interval": 5,
                    "github_token": "",
                    "window_pos": [],
                    "settings_dialog_pos": []
                },
                app_logger
            )
    
    def _save_config(self) -> bool:
        """
        保存配置文件
        
        Returns:
            bool: 保存是否成功
        """
        def _save_config_impl():
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            app_logger.info("配置文件保存成功")
            return True
        
        return handle_exception(
            "保存配置文件",
            _save_config_impl,
            False,
            app_logger
        )
    
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


def load_config() -> Dict[str, Any]:
    """加载配置文件，包含完整的错误处理和默认值"""
    manager = ConfigManager()
    # 由于使用了单例模式，这里直接返回内部配置的副本
    return manager._config.copy()


def save_config(cfg: Dict[str, Any]) -> bool:
    """
    保存配置文件
    
    Args:
        cfg: 配置字典
        
    Returns:
        bool: 保存是否成功
    """
    manager = ConfigManager()
    manager._config = cfg
    return manager._save_config()


def is_market_open():
    """检查A股是否开市"""
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))