#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会话缓存管理模块
用于缓存主界面的会话状态，包括股票数据、窗口位置等信息
"""

import json
import os
import time
from typing import Any, Dict, Optional

from .logger import app_logger

# 缓存文件路径
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"
)
CACHE_FILE = os.path.join(CACHE_DIR, "last_session.json")


def save_session_cache(data: Dict[str, Any]) -> bool:
    """
    保存会话缓存数据到文件

    Args:
        data (Dict[str, Any]): 要缓存的数据

    Returns:
        bool: 保存成功返回True，否则返回False
    """
    try:
        # 确保缓存目录存在
        os.makedirs(CACHE_DIR, exist_ok=True)

        # 添加时间戳
        cache_data = {"timestamp": time.time(), "data": data}

        # 写入缓存文件
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        app_logger.info(f"会话缓存保存成功: {CACHE_FILE}")
        return True
    except Exception as e:
        app_logger.error(f"保存会话缓存失败: {e}")
        return False


def load_session_cache(max_age: int = 86400) -> Optional[Dict[str, Any]]:  # 默认24小时
    """
    从文件加载会话缓存数据

    Args:
        max_age (int): 缓存最大有效时间（秒），默认86400秒（24小时）

    Returns:
        Optional[Dict[str, Any]]: 缓存数据，如果不存在、已过期或损坏则返回None
    """
    try:
        # 检查缓存文件是否存在
        if not os.path.exists(CACHE_FILE):
            app_logger.debug("会话缓存文件不存在")
            return None

        # 读取缓存文件
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # 检查时间戳
        timestamp = cache_data.get("timestamp", 0)
        if time.time() - timestamp > max_age:
            app_logger.debug("会话缓存已过期")
            # 删除过期的缓存文件
            try:
                os.remove(CACHE_FILE)
            except:
                pass
            return None

        app_logger.info("会话缓存加载成功")
        return cache_data.get("data", {})
    except Exception as e:
        app_logger.error(f"加载会话缓存失败: {e}")
        # 删除损坏的缓存文件
        try:
            os.remove(CACHE_FILE)
        except:
            pass
        return None


def clear_session_cache() -> bool:
    """
    清除会话缓存文件

    Returns:
        bool: 清除成功返回True，否则返回False
    """
    try:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            app_logger.info("会话缓存已清除")
        return True
    except Exception as e:
        app_logger.error(f"清除会话缓存失败: {e}")
        return False
