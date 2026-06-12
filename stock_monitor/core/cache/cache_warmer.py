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

    def __init__(self, quant_engine, stock_fetcher, max_workers: int = 4):
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
        self.cache_stats["start_time"] = time.time()

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

        self.cache_stats["end_time"] = time.time()
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
                    except Exception:
                        pass

                    # 2. OBV指标
                    try:
                        self.engine.detect_obv_accumulation(symbol, bars_df)
                    except Exception:
                        pass

                except Exception as e:
                    app_logger.debug(f"预热 {symbol} 周期 {category} 时出错：{e}")
                    continue

            return True

        except Exception as e:
            app_logger.error(f"符号 {symbol} 缓存预热失败：{e}")
            return False

    def clear_caches(self):
        """清空所有缓存

        用于测试或手动重置缓存
        """
        try:
            # 清空引擎中的所有缓存（通过公开方法）
            self.engine.clear_all_caches()

            app_logger.info("所有缓存已清空")
            return True
        except Exception as e:
            app_logger.error(f"清空缓存失败：{e}")
            return False

    def get_cache_status(self) -> dict:
        """获取当前缓存状态统计

        Returns:
            缓存统计信息（命中率、大小等）
        """
        status = {
            "warming_stats": self.cache_stats.copy(),
            "engine_caches": {},
        }

        # 添加引擎缓存统计
        try:
            if hasattr(self.engine, "_avg_vol_cache"):
                status["engine_caches"]["avg_vol"] = (
                    self.engine._avg_vol_cache.get_stats()
                )
            if hasattr(self.engine, "_auction_cache"):
                status["engine_caches"]["auction"] = (
                    self.engine._auction_cache.get_stats()
                )
            if hasattr(self.engine, "_large_order_cache"):
                status["engine_caches"]["large_order"] = (
                    self.engine._large_order_cache.get_stats()
                )
        except Exception as e:
            app_logger.debug(f"获取缓存统计信息失败：{e}")

        return status


class PerformanceMonitor:
    """性能监测器 - 跟踪扫描速度和缓存效果"""

    def __init__(self):
        """初始化性能监测器"""
        self.scan_times = []  # 最近的扫描耗时记录
        self.cache_hits_trend = []  # 缓存命中率趋势
        self.max_records = 100  # 保留最多100条记录

    def record_scan_time(self, duration_seconds: float):
        """记录一次扫描的耗时

        Args:
            duration_seconds: 扫描耗时（秒）
        """
        self.scan_times.append(duration_seconds)
        if len(self.scan_times) > self.max_records:
            self.scan_times.pop(0)

    def record_cache_hits(self, hit_rate: float):
        """记录缓存命中率

        Args:
            hit_rate: 命中率 (0-100)
        """
        self.cache_hits_trend.append(hit_rate)
        if len(self.cache_hits_trend) > self.max_records:
            self.cache_hits_trend.pop(0)

    def get_statistics(self) -> dict:
        """获取性能统计信息

        Returns:
            性能指标统计
        """
        if not self.scan_times:
            return {"scans": 0, "avg_time": 0, "min_time": 0, "max_time": 0}

        return {
            "scans": len(self.scan_times),
            "avg_time": sum(self.scan_times) / len(self.scan_times),
            "min_time": min(self.scan_times),
            "max_time": max(self.scan_times),
            "avg_cache_hit_rate": (
                sum(self.cache_hits_trend) / len(self.cache_hits_trend)
                if self.cache_hits_trend
                else 0
            ),
        }

    def format_statistics(self) -> str:
        """格式化性能统计为可读的字符串

        Returns:
            格式化的统计信息字符串
        """
        stats = self.get_statistics()
        if stats["scans"] == 0:
            return "暂无扫描数据"

        return (
            f"扫描次数: {stats['scans']}, "
            f"平均耗时: {stats['avg_time']:.1f}s, "
            f"最快: {stats['min_time']:.1f}s, "
            f"最慢: {stats['max_time']:.1f}s, "
            f"平均缓存命中率: {stats['avg_cache_hit_rate']:.0f}%"
        )
