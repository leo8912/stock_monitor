"""股票管理模块
负责处理股票相关的业务逻辑
"""

import concurrent.futures
import json
import threading
from typing import Any

from stock_monitor.core.engine.quant_engine import QuantEngine
from stock_monitor.core.engine.quant_engine_constants import MAX_CACHE_SIZE
from stock_monitor.models.stock_data import StockRowData
from stock_monitor.utils.logger import app_logger
from stock_monitor.utils.stock_utils import StockCodeProcessor


def get_dynamic_lru_cache_size() -> int:
    """获取动态LRU缓存大小配置。返回默认值以兼容旧API。"""
    return MAX_CACHE_SIZE


class StockManager:
    """股票管理器"""

    def __init__(self, stock_data_service=None):
        """初始化股票管理器"""
        self._processor = StockCodeProcessor()
        # 缓存上一帧的股票数据，用于差异比较 (元组提升比较性能，减少字符串拼接开销)
        self._last_stock_data: dict[str, tuple] = {}
        # 使用依赖注入，如果没有提供则使用全局实例
        from stock_monitor.core.stock_service import (
            stock_data_service as global_stock_data_service,
        )

        self._stock_data_service = stock_data_service or global_stock_data_service
        self._quant_engine = None  # 延迟初始化
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._large_orders_cache = {}
        self._auction_cache = {}  # [NEW] 集合竞价缓存
        # 线程安全锁 - 保护缓存读写
        self._cache_lock = threading.Lock()

    def has_stock_data_changed(self, stocks: list[StockRowData]) -> bool:
        """检查股票数据是否发生变化"""
        if not self._last_stock_data:
            return True

        for stock in stocks:
            if stock.name not in self._last_stock_data:
                return True
            if self._last_stock_data[stock.name] != stock.hash_key:
                return True

        current_names = [s.name for s in stocks]
        for name in self._last_stock_data.keys():
            if name not in current_names:
                return True
        return False

    def update_last_stock_data(self, stocks: list[StockRowData]) -> None:
        """更新最后股票数据缓存"""
        self._last_stock_data.clear()
        for stock in stocks:
            self._last_stock_data[stock.name] = stock.hash_key
        app_logger.debug(f"更新股票数据缓存，共{len(self._last_stock_data)}只股票")

    def _async_fetch_quant_data(self, codes: list[str]):
        """异步拉取量化数据（含大单流向与集合竞价），不阻塞主刷新线程"""
        if self._quant_engine is None:
            if hasattr(self._stock_data_service, "fetcher") and getattr(
                self._stock_data_service.fetcher, "mootdx_client", None
            ):
                self._quant_engine = QuantEngine(
                    self._stock_data_service.fetcher.mootdx_client
                )
            else:
                return

        for code in codes:
            try:
                # 1. 大单流向
                res = self._quant_engine.fetch_large_orders_flow(code)

                # 2. 集合竞价分析 [NEW]
                import time

                now_hm = time.strftime("%H:%M")
                auc_res = None
                # 仅在盘前或开盘初期关注竞价
                if "09:00" <= now_hm <= "10:00" or "15:00" <= now_hm <= "17:00":
                    auc_res = self._quant_engine.fetch_call_auction_data(code)

                # 线程安全地更新缓存
                with self._cache_lock:
                    self._large_orders_cache[code] = res
                    if auc_res is not None:
                        self._auction_cache[code] = auc_res
            except Exception as e:
                app_logger.warning(f"获取 {code} 量化数据失败: {e}")

    def fetch_and_process_stocks(
        self, stock_codes: list[str], sync_quant_data: bool = False
    ) -> tuple[list[StockRowData], int]:
        """获取并处理股票数据"""
        # 1. 批量获取基础行情数据
        data_dict = self._stock_data_service.get_multiple_stocks_data(stock_codes)

        # 2. 异步派发量化数据拉取任务 (大单+竞价)
        if sync_quant_data:
            self._async_fetch_quant_data(stock_codes)
        else:
            self._executor.submit(self._async_fetch_quant_data, stock_codes)

        # 3. 处理并整合数据
        failed_count = sum(1 for data in data_dict.values() if data is None)
        stocks = []
        for code in stock_codes:
            info = data_dict.get(code)
            if info:
                # 线程安全地从缓存读取异步大单结果
                with self._cache_lock:
                    large_order_vol = self._large_orders_cache.get(
                        code, (0.0, 0.0, 0.0)
                    )
                    auction_data = self._auction_cache.get(code, {})
                info["large_order_vol"] = large_order_vol
                # 注入竞价数据 [NEW]
                info["auction_data"] = auction_data

                try:
                    info_json = json.dumps(info, sort_keys=True)
                    stock_item = self._process_single_stock_data(code, info_json)
                except Exception:
                    stock_item = self._process_single_stock_data_impl(code, info)
                stocks.append(stock_item)
            else:
                stocks.append(
                    StockRowData(
                        code=code,
                        name=code,
                        price="--",
                        change_str="--",
                        color_hex="#e6eaf3",
                        seal_vol="",
                        seal_type="",
                    )
                )

        app_logger.debug(f"共处理 {len(stocks)} 只股票数据")
        return stocks, failed_count

    def get_stock_list_data(self, stock_codes: list[str]) -> list[StockRowData]:
        """获取股票列表数据"""
        stocks, _ = self.fetch_and_process_stocks(stock_codes)
        return stocks

    def get_all_market_data(self) -> dict[str, Any]:
        """
        获取全市场数据

        Returns:
            Dict[str, Any]: 全市场数据字典
        """
        return self._stock_data_service.get_all_market_data()

    def _process_single_stock_data_impl(
        self, code: str, info: dict[str, Any]
    ) -> StockRowData:
        """处理单只股票的数据的实际实现"""
        from stock_monitor.core.data.stock_data_processor import stock_processor

        result = stock_processor.process_raw_data(code, info)
        return result

    def _process_single_stock_data(self, code: str, info_json: str) -> StockRowData:
        """处理单只股票的数据"""
        try:
            info = json.loads(info_json) if isinstance(info_json, str) else info_json
        except Exception:
            info = {}

        return self._process_single_stock_data_impl(code, info)


# 创建全局股票管理器实例
stock_manager = StockManager()
