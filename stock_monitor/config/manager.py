import os
import json
import shutil
from typing import Dict, Any, Optional, Union, List
from ..utils.logger import app_logger
from ..utils.helpers import handle_exception

# 配置文件路径 - 存储在用户目录中，避免更新时丢失
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.stock_monitor')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

# 确保配置目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config() -> Dict[str, Any]:
    """加载配置文件，包含完整的错误处理和默认值"""
    def _load_config():
        if not os.path.exists(CONFIG_PATH):
            # 创建默认配置文件
            default_config = {
                "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                "refresh_interval": 5,
                "github_token": "",
                "window_pos": [],
                "settings_dialog_pos": []
            }
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
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
            
        return config
    
    def _handle_json_decode_error():
        # 如果JSON解析失败，备份原文件并创建新配置
        error_msg = f"配置文件损坏，正在创建新的配置文件..."
        app_logger.error(error_msg)
        print(error_msg)
        
        if os.path.exists(CONFIG_PATH):
            # 备份原文件
            backup_path = CONFIG_PATH + ".bak"
            shutil.copy2(CONFIG_PATH, backup_path)
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
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        app_logger.info(f"默认配置文件已创建: {CONFIG_PATH}")
        return default_config
    
    def _handle_permission_error():
        error_msg = "配置文件权限错误，请检查文件权限"
        app_logger.error(error_msg)
        print(error_msg)
        return {
            "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
            "refresh_interval": 5,
            "github_token": "",
            "window_pos": [],
            "settings_dialog_pos": []
        }
    
    try:
        return _load_config()
    except json.JSONDecodeError:
        return handle_exception(
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
        return handle_exception(
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
        return handle_exception(
            "加载配置文件",
            _load_config,
            {
                "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                "refresh_interval": 5,
                "github_token": "",
                "window_pos": [],
                "settings_dialog_pos": []
            },
            app_logger
        )


def save_config(cfg: Dict[str, Any]) -> None:
    """
    保存配置文件
    
    Args:
        cfg: 配置字典
    """
    def _save_config():
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        app_logger.info("配置文件保存成功")
    
    handle_exception(
        "保存配置文件",
        _save_config,
        None,
        app_logger
    )


def is_market_open():
    """检查A股是否开市"""
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))