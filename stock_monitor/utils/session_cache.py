#!/usr/bin/env python3

"""
会话缓存管理模块
用于缓存主界面的会话状态，包括股票数据、窗口位置等信息

写入策略：
- 默认节流：距上次落盘 < MIN_SAVE_INTERVAL 秒时只保留 pending，由 Timer 延迟写
- force=True：立即写入（退出 / 隐藏窗口）
- 所有实际写盘都在 _write_lock 内串行，避免 force 与后台写并发损坏文件
"""

import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from stock_monitor.config.manager import get_config_dir

from .logger import app_logger

LEGACY_CACHE_DIR = (
    Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "cache"
)
CACHE_DIR = Path(get_config_dir()) / "cache"
CACHE_FILE = CACHE_DIR / "last_session.json"

MIN_SAVE_INTERVAL = 30.0
_DEBOUNCE_DELAY = 1.0

_write_lock = threading.RLock()
_pending_data: dict[str, Any] | None = None
_last_save_ts = 0.0
_debounce_timer: threading.Timer | None = None


def _migrate_legacy_session_cache_if_needed() -> None:
    """将旧版仓库内会话缓存迁移到用户目录。"""
    legacy_cache_file = LEGACY_CACHE_DIR / "last_session.json"
    if CACHE_FILE.exists() or not legacy_cache_file.exists():
        return

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_cache_file, CACHE_FILE)
        app_logger.info(f"已迁移旧会话缓存: {legacy_cache_file} -> {CACHE_FILE}")
    except Exception as e:
        app_logger.warning(f"迁移旧会话缓存失败，将继续使用新目录: {e}")


def _write_cache_file_unlocked(data: dict[str, Any]) -> bool:
    """写入缓存文件；调用方必须已持有 _write_lock。"""
    global _last_save_ts
    try:
        _migrate_legacy_session_cache_if_needed()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_data = {"timestamp": time.time(), "data": data}
        temp_file = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.tmp")
        with open(temp_file, "w", encoding="utf-8", buffering=1 << 16) as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, CACHE_FILE)
        _last_save_ts = time.time()
        app_logger.debug(f"会话缓存保存成功: {CACHE_FILE}")
        return True
    except Exception as e:
        app_logger.error(f"保存会话缓存失败: {e}")
        return False


def _flush_pending_locked() -> bool:
    """必须在 _write_lock 下调用：取出 pending 并写盘。"""
    global _pending_data
    data = _pending_data
    if data is None:
        return True
    _pending_data = None
    return _write_cache_file_unlocked(data)


def _schedule_debounce() -> None:
    global _debounce_timer

    def _fire() -> None:
        global _pending_data
        with _write_lock:
            data = _pending_data
            if data is None:
                return
            if time.time() - _last_save_ts < MIN_SAVE_INTERVAL:
                delay = max(0.05, MIN_SAVE_INTERVAL - (time.time() - _last_save_ts))
                t = threading.Timer(delay, _fire)
                t.daemon = True
                _debounce_timer = t
                t.start()
                return
            _pending_data = None
            _write_cache_file_unlocked(data)

    with _write_lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
        if _last_save_ts == 0.0:
            delay = _DEBOUNCE_DELAY
        else:
            delay = max(
                _DEBOUNCE_DELAY, MIN_SAVE_INTERVAL - (time.time() - _last_save_ts)
            )
        t = threading.Timer(delay, _fire)
        t.daemon = True
        _debounce_timer = t
    t.start()


def save_session_cache(data: dict[str, Any], *, force: bool = False) -> bool:
    """
    保存会话缓存数据。

    Args:
        data: 要缓存的数据
        force: True 时绕过节流立即同步写盘

    Returns:
        force 写盘成功 True；节流路径排队成功返回 True
    """
    global _pending_data

    if force:
        with _write_lock:
            if _debounce_timer is not None:
                _debounce_timer.cancel()
            _pending_data = data
            return _flush_pending_locked()

    with _write_lock:
        _pending_data = data
    _schedule_debounce()
    return True


def flush_session_cache() -> bool:
    """立即写出 pending 会话缓存（关机路径调用）。"""
    with _write_lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
        return _flush_pending_locked()


def load_session_cache(max_age: int = 86400) -> dict[str, Any] | None:  # 默认24小时
    """从文件加载会话缓存数据。"""
    try:
        _migrate_legacy_session_cache_if_needed()
        if not CACHE_FILE.exists():
            app_logger.debug("会话缓存文件不存在")
            return None

        with open(CACHE_FILE, encoding="utf-8") as f:
            cache_data = json.load(f)

        timestamp = cache_data.get("timestamp", 0)
        if time.time() - timestamp > max_age:
            app_logger.debug("会话缓存已过期")
            try:
                CACHE_FILE.unlink()
            except Exception:
                pass
            return None

        app_logger.info("会话缓存加载成功")
        return cache_data.get("data", {})
    except Exception as e:
        app_logger.error(f"加载会话缓存失败: {e}")
        try:
            CACHE_FILE.unlink()
        except Exception:
            pass
        return None
