"""
量化信号缓存的磁盘持久化纯函数实现。

从 :class:`~stock_monitor.core.workers.quant_worker.QuantWorker` 抽离的
信号缓存读写逻辑：payload 的解析/构建与原子写文件均为无状态函数，
由 QuantWorker 传入路径与状态快照，便于独立测试。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

KEY_SEPARATOR = "::"


def parse_cache_payload(
    data: dict, now: float, expiry_seconds: int
) -> tuple[dict, dict, int]:
    """解析磁盘缓存内容。

    Args:
        data: 磁盘 JSON 内容，key 格式 ``"symbol::signal_name"``，
            value 兼容旧格式（时间戳）和新格式（状态对象）。
        now: 当前时间戳，用于过期判定。
        expiry_seconds: 过期阈值（秒）。

    Returns:
        (last_signal_time, signal_states, expired_count)
    """
    last_signal_time: dict = {}
    signal_states: dict = {}
    for key_str, value in data.items():
        parts = key_str.split(KEY_SEPARATOR)
        if len(parts) != 2:
            continue
        key_tuple = (parts[0], parts[1])

        # 兼容旧格式（仅时间戳）和新格式（状态对象）
        if isinstance(value, dict):
            # 新格式：{"last_score": int, "last_push_ts": float}
            signal_states[key_tuple] = value
            last_signal_time[key_tuple] = value.get("last_push_ts", 0)
        else:
            # 旧格式：直接是时间戳
            last_signal_time[key_tuple] = value

    # 清理过期缓存项
    expired_keys = [k for k, v in last_signal_time.items() if now - v > expiry_seconds]
    for key in expired_keys:
        del last_signal_time[key]
        signal_states.pop(key, None)

    return last_signal_time, signal_states, len(expired_keys)


def build_cache_payload(signal_states: dict) -> dict:
    """将 tuple key 的信号状态字典序列化为磁盘 JSON 格式。"""
    return {
        f"{symbol}{KEY_SEPARATOR}{sig_name}": state
        for (symbol, sig_name), state in signal_states.items()
    }


def atomic_write_json(path: Path, data: dict) -> None:
    """原子写 JSON 文件（G-12：临时文件 + os.replace）。

    每个线程使用独立临时文件名，避免并发写同一临时文件；
    替换失败时清理残留临时文件。
    """
    tmp_path = path.parent / f"{path.name}.tmp{threading.get_ident()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
