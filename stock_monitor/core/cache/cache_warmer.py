"""
缓存预热引擎 - 性能优化模块
在应用启动时预加载K线数据和指标缓存，加速扫描速度
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_monitor.utils.logger import app_logger


class CacheWarmer:
    """缓存预热管理器

    功能:
    1. 批量预加载K线数据
    2. 预计算常用指标缓存
    3. 监测缓存预热进度
    """

    def __init__(self, quant_engine, stock_fetcher, max_workers: int = 4) -> None:
        """初始化缓存预热器

        Args:
            quant_engine: QuantEngine 实例
            stock_fetcher: StockDataFetcher 实例
            max_workers: 并行预热线程数
        """
        self.engine = quant_engine
        self.fetcher = stock_fetcher
        self.max_workers = max_workers
        self.cache_stats = {
            "total_symbols": 0,
            "warmed_symbols": 0,
            "failed_symbols": 0,
            "start_time": 0,
            "end_time": 0,
            "duration_seconds": 0,
        }

    def warm_cache_for_symbols(
        self, symbols: list[str], categories: list[int] = None, offset: int = 100
    ) -> dict:
        """批量预热指定股票的缓存

        Args:
            symbols: 股票代码列表
            categories: K线周期列表 (默认: [1, 2, 3, 9] = 15m/30m/60m/daily)
            offset: 获取K线数量 (默认: 100)

        Returns:
            缓存预热统计信息
        """
        if categories is None:
            categories = [1, 2, 3, 9]  # 15m, 30m, 60m, daily

        self.cache_stats["total_symbols"] = len(symbols)
        self.cache_stats["warmed_symbols"] = 0
        self.cache_stats["failed_symbols"] = 0
        self.cache_stats["start_time"] = time.perf_counter()

        app_logger.info(
            f"开始缓存预热：{len(symbols)} 只股票，周期数 {len(categories)}，"
            f"并发线程 {self.max_workers}"
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._warm_single_symbol, symbol, categories, offset
                ): symbol
                for symbol in symbols
            }

            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    success = future.result(timeout=30)
                    if success:
                        self.cache_stats["warmed_symbols"] += 1
                    else:
                        self.cache_stats["failed_symbols"] += 1
                except Exception as e:
                    app_logger.warning(f"预热股票 {symbol} 缓存失败：{e}")
                    self.cache_stats["failed_symbols"] += 1

        self.cache_stats["end_time"] = time.perf_counter()
        self.cache_stats["duration_seconds"] = (
            self.cache_stats["end_time"] - self.cache_stats["start_time"]
        )

        app_logger.info(
            f"缓存预热完成：成功 {self.cache_stats['warmed_symbols']}/"
            f"{self.cache_stats['total_symbols']}，"
            f"失败 {self.cache_stats['failed_symbols']}，"
            f"耗时 {self.cache_stats['duration_seconds']:.1f}s"
        )

        return self.cache_stats

    def _warm_single_symbol(
        self, symbol: str, categories: list[int], offset: int
    ) -> bool:
        """单个股票的缓存预热（供线程池调用）

        Args:
            symbol: 股票代码
            categories: K线周期列表
            offset: K线数量

        Returns:
            是否预热成功
        """
        try:
            # 预加载各个周期的K线数据
            for category in categories:
                try:
                    bars_df = self.engine.fetch_bars(
                        symbol, category=category, offset=offset
                    )
                    if bars_df is None or bars_df.empty:
                        app_logger.debug(f"符号 {symbol} 周期 {category} 数据为空")
                        continue

                    # 预计算常用指标缓存
                    # 1. RSRS指标（快速计算，缓存结果）
                    try:
                        rsrs_z, _ = self.engine.calculate_rsrs(bars_df)
                    except Exception as e:
                        app_logger.debug(
                            f"预热 {symbol} 周期 {category} RSRS 计算失败：{e}",
                            exc_info=True,
                        )

                    # 2. OBV指标
                    try:
                        self.engine.detect_obv_accumulation(symbol, bars_df)
                    except Exception as e:
                        app_logger.debug(
                            f"预热 {symbol} 周期 {category} OBV 计算失败：{e}",
                            exc_info=True,
                        )

                except Exception as e:
                    app_logger.debug(f"预热 {symbol} 周期 {category} 时出错：{e}")
                    continue

            return True

        except Exception as e:
            app_logger.error(f"符号 {symbol} 缓存预热失败：{e}")
            return False
