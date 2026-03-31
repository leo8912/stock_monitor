import json
import os

import pandas as pd

from stock_monitor.config.manager import get_config_dir
from stock_monitor.utils.logger import app_logger


class MootdxNameRegistry:
    """负责单独管理 mootdx 标的名称的手工缓存和更新映射"""

    def __init__(self, mootdx_client=None, parent=None):
        self.mootdx_client = mootdx_client
        self._parent = parent  # 持有父对象引用以访问延迟初始化的 client
        self._name_cache = self._load_name_cache()

    def update_client(self, client):
        """更新 mootdx client 引用"""
        self.mootdx_client = client

    def _get_mootdx_client(self):
        """获取 mootdx client，支持延迟初始化"""
        if self._parent is not None:
            # 通过父对象的 property 触发延迟初始化
            return self._parent.mootdx_client
        return self.mootdx_client

    def _get_name_cache_file(self):
        return os.path.join(get_config_dir(), "mootdx_names.json")

    def _load_name_cache(self):
        cache_file = self._get_name_cache_file()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    # 清洗可能存在的 \x00
                    return {
                        k: str(v).replace("\x00", "").strip() for k, v in data.items()
                    }
            except Exception:
                pass
        return {}

    def _save_name_cache(self):
        cache_file = self._get_name_cache_file()
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._name_cache, f, ensure_ascii=False)
        except Exception as e:
            app_logger.error(f"保存缓存失败: {e}")

    def sync_mootdx_names(self):
        """全量同步 mootdx 名称字典"""
        # 通过 _get_mootdx_client 获取 client，支持延迟初始化
        client = self._get_mootdx_client()
        if client is None:
            app_logger.warning("mootdx client 未初始化，跳过名称同步")
            return
        app_logger.info("本地缓存中存在未知名称，触发 mootdx 全量字典同步...")
        try:
            sz_df = client.stocks(market=0)
            sh_df = client.stocks(market=1)
            full_df = pd.concat([sz_df, sh_df])
            for _, row in full_df.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).replace("\x00", "").strip()
                self._name_cache["sh" + code] = name
                self._name_cache["sz" + code] = name
                self._name_cache[code] = name

            self._save_name_cache()
            app_logger.info(f"全量字典同步完毕，共计 {len(full_df)} 只标的写入缓存。")
        except Exception as e:
            # 使用 print 作为兜底，防止日志系统已关闭
            try:
                app_logger.error(f"全量同步 mootdx 名称字典失败：{e}")
            except (ValueError, AttributeError):
                # 日志系统可能已关闭，使用标准输出
                print(f"ERROR: 全量同步 mootdx 名称字典失败：{e}")

    def get_name(self, code: str) -> str:
        """从缓存安全获取名称"""
        return self._name_cache.get(code, code)

    def resolve_missing(self, missing_codes: list[str]):
        """若存在缺失则批量挂起同步，并设置兜底"""
        if not missing_codes:
            return
        # 尝试同步名称（如果 client 可用）
        # 注意：sync_mootdx_names 内部会检查 client 是否为 None
        self.sync_mootdx_names()
        # 为所有缺失的代码设置兜底值
        for c in missing_codes:
            if c not in self._name_cache:
                self._name_cache[c] = c
