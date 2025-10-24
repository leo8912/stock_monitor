import os
import json
import shutil
from typing import Dict, Any, Optional, Union, List
from ..utils.logger import app_logger

# 配置文件路径 - 修正路径，确保指向正确位置
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def load_config() -> Dict[str, Any]:
    """加载配置文件，包含完整的错误处理和默认值"""
    try:
        if not os.path.exists(CONFIG_PATH):
            # 创建默认配置文件
            default_config = {
                "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
                "refresh_interval": 5,
                "github_token": "",
                "window_pos": None,
                "settings_dialog_pos": None
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
            config['window_pos'] = None
        if 'settings_dialog_pos' not in config:
            config['settings_dialog_pos'] = None
            
        return config
    except json.JSONDecodeError as e:
        # 如果JSON解析失败，备份原文件并创建新配置
        error_msg = f"配置文件损坏，JSON解析错误: {e}，正在创建新的配置文件..."
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
            "window_pos": None,
            "settings_dialog_pos": None
        }
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            app_logger.info(f"默认配置文件已创建: {CONFIG_PATH}")
        except Exception as save_error:
            save_error_msg = f"创建默认配置文件失败: {save_error}"
            app_logger.error(save_error_msg)
            print(save_error_msg)
        return default_config
    except PermissionError as e:
        error_msg = f"配置文件权限错误: {e}，请检查文件权限"
        app_logger.error(error_msg)
        print(error_msg)
        return {
            "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
            "refresh_interval": 5,
            "github_token": "",
            "window_pos": None,
            "settings_dialog_pos": None
        }
    except Exception as e:
        error_msg = f"加载配置文件时发生未知错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)
        return {
            "user_stocks": ["sh600460", "sh603986", "sh600030", "sh000001"],
            "refresh_interval": 5,
            "github_token": "",
            "window_pos": None,
            "settings_dialog_pos": None
        }

def save_config(cfg: Dict[str, Any]) -> None:
    """
    保存配置文件
    
    Args:
        cfg: 配置字典
    """
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        app_logger.info("配置文件保存成功")
    except Exception as e:
        error_msg = f"保存配置文件时发生错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)

def is_market_open():
    """检查A股是否开市"""
    import datetime
    now = datetime.datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    t = now.time()
    return ((datetime.time(9,30) <= t <= datetime.time(11,30)) or 
            (datetime.time(13,0) <= t <= datetime.time(15,0)))