"""
股票数据获取模块
负责从各种数据源获取原始股票数据

数据源:
  - A股实时行情: MarketDataAdapter (easyquotation 腾讯/新浪)
  - 港股实时行情: easyquotation hkquote
"""

import atexit
import concurrent.futures
import time
from typing import Any, Optional

import easyquotation

from stock_monitor.core.data.market_data_adapter import MarketDataAdapter
from stock_monitor.core.resolvers.mootdx_registry import MootdxNameRegistry
from stock_monitor.utils.error_handler import safe_call
from stock_monitor.utils.logger import app_logger

# 常量定义
MAX_RETRY_ATTEMPTS = 5  # 股票数据获取最大重试次数
RETRY_DELAY_SECONDS = 2  # 重试间隔(秒)


class StockDataFetcher:
    """股票数据获取类"""

    def _init_hk_quotation(self):
        return easyquotation.use("hkquote")

    def __init__(self):
        """初始化数据获取器"""
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # 市场数据适配器（替代 mootdx）
        self._market_adapter = None
        # 备用数据源：新浪接口客户端（延迟初始化）
        self._sina_client = None

        # 传入 self 引用，让 name_registry 可以访问父对象
        self.name_registry = MootdxNameRegistry(parent=self)

        # 注册应用退出清理钩子，防止句柄泄露
        atexit.register(self.close)

    @property
    def market_adapter(self):
        """延迟初始化 MarketDataAdapter - 只在第一次访问时创建"""
        if self._market_adapter is None:
            try:
                app_logger.info("初始化 MarketDataAdapter...")
                self._market_adapter = MarketDataAdapter()
                app_logger.info("MarketDataAdapter 初始化成功")
                # 更新 name_registry 的 client
                self.name_registry.mootdx_client = self._market_adapter
            except Exception as e:
                import traceback

                error_detail = traceback.format_exc()
                app_logger.error(f"初始化 MarketDataAdapter 失败：{e}")
                app_logger.error(f"详细错误堆栈:\n{error_detail}")
                self._market_adapter = None
        return self._market_adapter

    # 向后兼容属性: 兼容旧代码通过 mootdx_client 访问
    @property
    def mootdx_client(self):
        """向后兼容: 返回 MarketDataAdapter 实例"""
        return self.market_adapter

    @property
    def sina_client(self):
        """延迟初始化 sina 备用行情客户端"""
        if self._sina_client is None:
            try:
                self._sina_client = easyquotation.use("sina")
                app_logger.info("Sina 备用行情引擎初始化成功")
            except Exception as e:
                app_logger.error(f"初始化 Sina 备用行情引擎失败：{e}")
                self._sina_client = None
        return self._sina_client

    def close(self):
        """释放网络资源与线程池"""
        # 注意：此处在 atexit 触发时，不要调用 app_logger，否则会导致 ValueError: I/O operation on closed file

        # 1. 停止线程池
        if hasattr(self, "_executor") and self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)

    def get_quotation_engine(self, code: str):
        """
        根据股票代码获取相应的行情引擎
        """
        if code.startswith("hk"):
            quotation_engine = safe_call(
                self._init_hk_quotation,
                default_return=None,
                exception_handler=lambda e, error_type: (
                    app_logger.error(f"初始化港股行情引擎失败: {e}") or None
                ),
            )
            if quotation_engine:
                app_logger.debug(f"使用 hkquote 引擎获取港股 {code} 数据")
            return quotation_engine
        return None

    def fetch_single_stock(
        self, quotation_engine, code: str, query_code: str
    ) -> Optional[dict[str, Any]]:
        """
        从行情引擎获取单只股票数据

        Args:
            quotation_engine: 行情引擎
            code: 完整股票代码(带前缀)
            query_code: 查询用代码(可能不带前缀)

        Returns:
            股票数据字典或None
        """
        try:
            if code.startswith(("sh", "sz")):
                # A股:使用prefix=True参数,用完整代码作为键
                single = quotation_engine.stocks(code, prefix=True)
                return single if isinstance(single, dict) and code in single else None
            elif code.startswith("hk"):
                # 港股:移除前缀查询
                single = quotation_engine.stocks(query_code)
                return single if isinstance(single, dict) else None
            else:
                # 其他:使用纯代码查询
                single = quotation_engine.stocks(query_code)
                return single if isinstance(single, dict) else None
        except Exception as e:
            app_logger.debug(f"获取股票 {code} 数据时发生异常: {e}")
            return None

    def fetch_with_retry(self, quotation_engine, code: str) -> Optional[dict[str, Any]]:
        """
        带重试机制获取股票数据

        Args:
            quotation_engine: 行情引擎
            code (str): 股票代码

        Returns:
            Optional[Dict[str, Any]]: 股票数据或None
        """
        # 准备查询代码(移除前缀)
        query_code = code[2:] if code.startswith(("sh", "sz", "hk")) else code

        # 首次尝试
        stock_data = self.fetch_single_stock(quotation_engine, code, query_code)
        if stock_data is not None:
            return stock_data

        # 重试机制
        for retry_count in range(1, MAX_RETRY_ATTEMPTS + 1):
            app_logger.debug(f"获取 {code} 数据失败,第 {retry_count} 次重试")
            # 指数退避：0.5s, 1s, 2s, 4s, 8s
            delay = min(0.5 * (2 ** (retry_count - 1)), 8.0)
            time.sleep(delay)

            stock_data = self.fetch_single_stock(quotation_engine, code, query_code)
            if stock_data is not None:
                return stock_data

        return None

    def fetch_single(self, code: str) -> Optional[dict[str, Any]]:
        """
        获取单只股票数据,带重试机制

        Args:
            code (str): 股票代码

        Returns:
            Optional[Dict[str, Any]]: 股票数据,获取失败则返回None
        """
        try:
            quotation_engine = self.get_quotation_engine(code)
            if quotation_engine is None:
                return None

            stock_data = self.fetch_with_retry(quotation_engine, code)
            return stock_data
        except Exception as e:
            app_logger.error(f"获取股票 {code} 数据失败: {e}")
            return None

    def fetch_multiple(self, codes: list[str]) -> dict[str, Optional[dict[str, Any]]]:
        """
        批量获取多只股票数据,按市场类型分组处理

        Args:
            codes (List[str]): 股票代码列表

        Returns:
            Dict[str, Optional[Dict[str, Any]]]: 股票数据字典,键为股票代码,值为股票数据或None
        """
        import threading

        result = {}
        result_lock = threading.Lock()

        # 按市场类型分组
        sina_codes = []  # A股普通股票和指数
        hk_codes = []  # 港股

        for code in codes:
            if code.startswith("hk"):
                hk_codes.append(code)
            else:
                sina_codes.append(code)

        # 并发获取A股和港股数据
        futures = []
        if sina_codes:
            futures.append(
                self._executor.submit(
                    self._fetch_a_stocks, result, result_lock, sina_codes
                )
            )
        if hk_codes:
            futures.append(
                self._executor.submit(
                    self._fetch_hk_stocks, result, result_lock, hk_codes
                )
            )

        # 等待所有任务完成
        concurrent.futures.wait(futures)

        # 处理未能获取的数据
        for code in codes:
            if code not in result:
                result[code] = None

        return result

    def _fetch_a_stocks(self, result: dict, result_lock, sina_codes: list[str]):
        """
        批量获取A股数据，使用 MarketDataAdapter (easyquotation 腾讯/新浪)
        """
        fetched_count = 0
        try:
            adapter = self.market_adapter
            if adapter is not None:
                df = adapter.quotes(symbol=sina_codes)
                if df is not None and not df.empty:
                    records = df.to_dict("records")

                    # 1. 甄别需要查询名字的代码
                    missing_names = [
                        c for c in sina_codes if c == self.name_registry.get_name(c)
                    ]
                    if missing_names:
                        self.name_registry.resolve_missing(missing_names)

                    # 2. 拼接数据
                    with result_lock:
                        for row in records:
                            code = row.get("code", "")
                            if (
                                not code
                                or not isinstance(row, dict)
                                or "price" not in row
                            ):
                                continue
                            row["name"] = self.name_registry.get_name(code)
                            result[code] = row
                            fetched_count += 1
                else:
                    app_logger.warning("MarketDataAdapter quotes 返回空数据")
            else:
                app_logger.warning("MarketDataAdapter 不可用")
        except Exception as e:
            app_logger.warning(f"MarketDataAdapter 获取行情异常: {e}")

        # 降级：未获取到全部数据时，用 Sina 补充缺失的代码
        missing_codes = [c for c in sina_codes if c not in result]
        if missing_codes:
            self._fetch_sina_fallback(result, result_lock, missing_codes)

        total = sum(1 for c in sina_codes if c in result)
        app_logger.debug(
            f"A股行情获取完成: adapter={fetched_count}, 合计={total}/{len(sina_codes)}"
        )

    # 向后兼容: 旧方法名
    _fetch_mootdx_stocks = _fetch_a_stocks

    def _fetch_sina_fallback(self, result: dict, result_lock, codes: list[str]):
        """
        Sina 备用数据源：通过 easyquotation 获取缺失的 A 股行情
        easyquotation.sina 的 stocks() 方法返回格式:
            { '600519': { 'name': '贵州茅台', 'now': 1285.13, 'close': 1290.88, ... } }
        """
        if not codes:
            return

        try:
            client = self.sina_client
            if client is None:
                app_logger.warning("Sina 备用源不可用，跳过降级获取")
                return

            # sina 接口使用纯数字代码
            clean_codes = [c[2:] if c.startswith(("sh", "sz")) else c for c in codes]
            raw_data = client.stocks(clean_codes)

            if not raw_data:
                app_logger.warning("Sina 备用源返回空数据")
                return

            updated_count = 0
            with result_lock:
                for code, clean_code in zip(codes, clean_codes):
                    if clean_code in raw_data:
                        info = raw_data[clean_code]
                        # 统一字段名：easyquotation 已有 now/close/name，与下游兼容
                        result[code] = info
                        updated_count += 1

            app_logger.info(
                f"Sina 备用源成功获取 {updated_count}/{len(codes)} 只 A 股行情"
            )

        except Exception as e:
            app_logger.error(f"Sina 备用源获取行情失败: {e}")

    def _fetch_hk_stocks(self, result: dict, result_lock, hk_codes: list[str]):
        """
        批量获取港股数据
        Args:
            result (dict): 结果字典
            hk_codes (List[str]): 港股代码列表
        """
        try:
            # 初始化港股引擎
            quotation_engine = safe_call(
                self._init_hk_quotation,
                default_return=None,
                exception_handler=lambda e, error_type: (
                    app_logger.error(f"初始化港股行情引擎失败: {e}") or None
                ),
            )

            if quotation_engine:
                # 港股需要移除前缀
                query_codes = [code[2:] for code in hk_codes]

                def fetch_hk_stocks():
                    hk_data_raw = quotation_engine.stocks(query_codes)
                    # 将返回的数据键添加hk前缀
                    if isinstance(hk_data_raw, dict):
                        return {f"hk{k}": v for k, v in hk_data_raw.items()}
                    return {}

                hk_data = safe_call(
                    fetch_hk_stocks,
                    default_return={},
                    exception_handler=lambda e, error_type: (
                        app_logger.error(f"批量获取港股数据失败: {e}") or {}
                    ),
                )

                if hk_data:
                    with result_lock:
                        result.update(hk_data)
                    app_logger.debug(f"成功获取 {len(hk_data)} 只港股数据")
        except Exception as e:
            app_logger.error(f"批量获取港股数据时发生错误: {e}")

    # 大单流计算逻辑已转移至 QuantEngine


# 创建全局实例
stock_data_fetcher = StockDataFetcher()
