import os
import json
import sys
from pathlib import Path
from typing import Dict, Any, Union

# 添加日志支持
from ..utils.logger import app_logger

# 尝试获取配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')

def resource_path(relative_path: str) -> str:
    """获取资源文件路径，兼容PyInstaller打包和源码运行"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(getattr(sys, '_MEIPASS'), relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def load_config() -> Dict[str, Any]:
    """加载配置文件，包含完整的错误处理和默认值"""
    try:
        if not os.path.exists(CONFIG_PATH):
            app_logger.info("配置文件不存在，创建默认配置文件")
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
            app_logger.info(f"默认配置文件已创建: {CONFIG_PATH}")
            return default_config
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            app_logger.debug("配置文件加载成功")
            
        # 确保必要的键存在
        if 'user_stocks' not in config:
            config['user_stocks'] = ["sh600460", "sh603986", "sh600030", "sh000001"]
            app_logger.warning("配置文件缺少user_stocks字段，已设置默认值")
        if 'refresh_interval' not in config:
            config['refresh_interval'] = 5
            app_logger.warning("配置文件缺少refresh_interval字段，已设置默认值")
        if 'github_token' not in config:
            config['github_token'] = ""
            app_logger.warning("配置文件缺少github_token字段，已设置默认值")
        if 'window_pos' not in config:
            config['window_pos'] = None
            app_logger.warning("配置文件缺少window_pos字段，已设置默认值")
        if 'settings_dialog_pos' not in config:
            config['settings_dialog_pos'] = None
            app_logger.warning("配置文件缺少settings_dialog_pos字段，已设置默认值")
            
        return config
    except json.JSONDecodeError as e:
        # 如果JSON解析失败，备份原文件并创建新配置
        error_msg = f"配置文件损坏，JSON解析错误: {e}，正在创建新的配置文件..."
        app_logger.error(error_msg)
        print(error_msg)
        
        if os.path.exists(CONFIG_PATH):
            # 备份原文件
            backup_path = CONFIG_PATH + ".bak"
            import shutil
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
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        app_logger.debug("配置文件保存成功")
    except Exception as e:
        error_msg = f"保存配置文件时发生错误: {e}"
        app_logger.error(error_msg)
        print(error_msg)