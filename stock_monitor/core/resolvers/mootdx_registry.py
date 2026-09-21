import contextlib
import io
import json
import os
import sys

import pandas as pd

from stock_monitor.config.manager import get_config_dir
from stock_monitor.utils.logger import app_logger

from .symbol_resolver import SymbolResolver, SymbolType


def safe_log_info(msg: str) -> None:
    """安全的日志 info 方法，防止日志系统关闭导致异常。"""
    try:
        app_logger.info(msg)
    except Exception:
        # 日志系统不可用时的最后兜底输出（非普通日志，刻意用 print，故不替换）
        print(f"INFO: {msg}")


def safe_log_warning(msg: str) -> None:
    """安全的日志 warning 方法，防止日志系统关闭导致异常。"""
    try:
        app_logger.warning(msg)
    except Exception:
        # 日志系统不可用时的最后兜底输出（非普通日志，刻意用 print，故不替换）
        print(f"WARNING: {msg}")


def safe_log_error(msg: str) -> None:
    """安全的日志 error 方法，防止日志系统关闭导致异常。"""
    try:
        app_logger.error(msg)
    except Exception:
        # 日志系统不可用时的最后兜底输出（非普通日志，刻意用 print，故不替换）
        print(f"ERROR: {msg}")


class MootdxNameRegistry:
    """负责单独管理标的名称的手工缓存和更新映射

    原使用 mootdx stocks() 全量同步名称，现已切换为 easyquotation + 批量行情获取。
    缓存文件仍使用 mootdx_names.json 以保持向后兼容。
    """

    def __init__(self, mootdx_client=None, parent=None) -> None:
        """初始化名称登记表。

        Args:
            mootdx_client: 数据适配器 client，可为 None（后续通过 update_client 注入）。
            parent: 持有该登记表的父对象，用于延迟获取 client。
        """
        self.mootdx_client = mootdx_client
        self._parent = parent  # 持有父对象引用以访问延迟初始化的 client
        self._name_cache = self._load_name_cache()

    def update_client(self, client) -> None:
        """更新 MarketDataAdapter client 引用"""
        self.mootdx_client = client

    def _get_client(self):
        """获取 MarketDataAdapter client，支持延迟初始化"""
        if self._parent is not None:
            # 通过父对象的 property 触发延迟初始化
            adapter = getattr(self._parent, "market_adapter", None)
            if adapter is not None:
                return adapter
            # 向后兼容
            return getattr(self._parent, "mootdx_client", None)
        return self.mootdx_client

    def _get_name_cache_file(self) -> str:
        """返回名称缓存文件的绝对路径。"""
        return os.path.join(get_config_dir(), "mootdx_names.json")

    def _load_name_cache(self) -> dict:
        """从磁盘加载名称缓存，失败时返回空字典。"""
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

    def _save_name_cache(self) -> None:
        """将名称缓存写入磁盘，失败时记录错误但不抛出。"""
        cache_file = self._get_name_cache_file()
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self._name_cache, f, ensure_ascii=False)
        except Exception as e:
            # 使用安全的日志方法
            safe_log_error(f"保存缓存失败：{e}")

    def sync_mootdx_names(self) -> None:
        """全量同步名称字典（使用 MarketDataAdapter stocks() 方法）"""
        client = self._get_client()

        if client is None:
            safe_log_error("MarketDataAdapter client 为 None，无法同步名称")
            if self._parent is not None:
                try:
                    safe_log_error(f"parent: {self._parent}")
                    safe_log_error(
                        f"parent.market_adapter: {getattr(self._parent, 'market_adapter', 'N/A')}"
                    )
                except Exception as e:
                    safe_log_error(f"访问 parent 属性失败：{e}")
            return

        # 防御 PyInstaller 窗口模式下 sys.stdout/stderr 为 None 的问题
        # 使用 contextlib.redirect_stdout/redirect_stderr 替代全局替换，
        # 避免影响其他线程的输出。
        _sentinel = io.StringIO()
        real_stdout = sys.stdout or _sentinel
        real_stderr = sys.stderr or _sentinel
        # 如果 stdout/stderr 为 None（PyInstaller 无窗口模式），
        # 临时设置一个 StringIO 防止 write 崩溃，用完即还原。
        _patched_stdout = False
        _patched_stderr = False
        if sys.stdout is None:
            sys.stdout = _sentinel
            _patched_stdout = True
        if sys.stderr is None:
            sys.stderr = _sentinel
            _patched_stderr = True

        _stderr_capture = io.StringIO()

        safe_log_info("本地缓存中存在未知名称，触发全量名称字典同步...")
        try:
            safe_log_info(f"调用 client.stocks(market=0)，client 类型：{type(client)}")

            with contextlib.redirect_stdout(io.StringIO()), \
                 contextlib.redirect_stderr(_stderr_capture):
                sz_df = client.stocks(market=0)
                sh_df = client.stocks(market=1)

            safe_log_info(
                f"sz_df 获取成功，行数：{len(sz_df) if sz_df is not None else 'None'}"
            )
            safe_log_info(
                f"sh_df 获取成功，行数：{len(sh_df) if sh_df is not None else 'None'}"
            )

            full_df = pd.concat([sz_df, sh_df])
            safe_log_info(f"数据合并成功，总行数：{len(full_df)}")

            temp_names = {}
            for df, market in [(sz_df, 0), (sh_df, 1)]:
                if df is not None:
                    for _, row in df.iterrows():
                        code = str(row["code"])
                        name = str(row["name"])

                        # [ELEGANT] 使用 SymbolResolver 统一识别逻辑
                        config = SymbolResolver.resolve(code, market)
                        full_symbol = f"{SymbolResolver.get_market_prefix(config.market)}{config.code}"

                        # 特殊修正：如果是上证指数，确保名称正确
                        if (
                            config.type == SymbolType.INDEX
                            and config.code in ("000001", "999999")
                            and config.market == 1
                        ):
                            name = "上证指数"

                        # 存储带前缀的完整键
                        temp_names[full_symbol] = name

            self._name_cache.update(temp_names)

            # 最终兜底：确保上证指数 sh000001 不会被任何逻辑篡改
            self._name_cache["sh000001"] = "上证指数"

            # 保存缓存前检查是否有数据
            if (sz_df is not None and not sz_df.empty) or (
                sh_df is not None and not sh_df.empty
            ):
                self._save_name_cache()
                safe_log_info(f"全量字典同步完毕，共计 {len(full_df)} 只标的写入缓存。")
            else:
                safe_log_warning("获取到的数据为空")
        except Exception as e:
            import traceback

            error_detail = traceback.format_exc()
            error_msg = f"全量同步名称字典失败：{e}\n详细堆栈:\n{error_detail}"
            safe_log_error(error_msg)
        finally:
            # 还原为 None 占位的标准流（仅还原我们修补的部分）
            if _patched_stdout:
                sys.stdout = None
            if _patched_stderr:
                sys.stderr = None

    def get_name(self, symbol: str) -> str:
        """从缓存安全获取名称，支持通过 SymbolResolver 归一化键"""
        # 1. 尝试归一化键 (如 sh000001 -> sh999999)
        config = SymbolResolver.resolve(symbol)
        prefix = SymbolResolver.get_market_prefix(config.market)
        normalized_key = f"{prefix}{config.code}"

        # 2. 依次尝试：归一化键 -> 原始键 -> 原始键本身
        return self._name_cache.get(
            normalized_key, self._name_cache.get(symbol, symbol)
        )

    def resolve_missing(self, missing_codes: list[str]) -> None:
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
