import datetime
import json
import os
import threading
from typing import Optional

from stock_monitor.config.manager import get_config_dir
from stock_monitor.core.engine.quant_engine import QuantEngine
from stock_monitor.core.engine.quant_engine_constants import (
    BACKTEST_STOP_LOSS,
    BACKTEST_TARGET_PROFIT,
)
from stock_monitor.utils.logger import app_logger


class BacktestEngine:
    """
    策略回测引擎 — 真实历史胜率计算
    """

    def __init__(self, quant_engine: QuantEngine) -> None:
        """初始化回测引擎并加载持久化缓存。

        Args:
            quant_engine: 用于拉取 K 线与计算指标的 QuantEngine 实例。
        """
        self.qe = quant_engine
        self.target_profit = BACKTEST_TARGET_PROFIT
        self.stop_loss = BACKTEST_STOP_LOSS
        self._lock = threading.Lock()

        # 持久化文件路径
        config_dir = get_config_dir()
        self._cache_file = os.path.join(config_dir, "backtest_cache.json")

        # 结果缓存: {(symbol, category, date): result}
        self._cache = self._load_cache()

    # ------------------------------------------------------------------
    # 公共回测框架
    # ------------------------------------------------------------------

    def _run_backtest(
        self,
        df,
        signal_points: list[int],
        hold_len: int,
        target_profit: float,
        stop_loss: float,
    ) -> dict:
        """对信号点列表执行统一的持仓期盈亏评估。

        所有策略回测方法共享此框架，避免重复的评估循环。
        """
        n = len(signal_points)
        if n == 0:
            return {"total_signals": 0, "win_rate": 0.0, "avg_profit": 0.0}

        success_count = 0
        total_profit = 0.0
        for idx in signal_points:
            entry_price = df.loc[idx, "close"]
            if entry_price <= 0:  # 除零防护（T12）
                continue
            future_df = df.iloc[idx + 1 : idx + 1 + hold_len]
            if future_df.empty:
                continue
            max_high = future_df["high"].max()
            min_low = future_df["low"].min()
            exit_price = future_df["close"].iloc[-1]

            if (max_high - entry_price) / entry_price >= target_profit:
                success_count += 1
                total_profit += target_profit
            elif (min_low - entry_price) / entry_price <= -stop_loss:
                total_profit -= stop_loss
            else:
                total_profit += (exit_price - entry_price) / entry_price

        return {
            "total_signals": n,
            "win_rate": round(success_count / n, 4),
            "avg_profit": round(total_profit / n, 4),
        }

    def _precompute_rsrs_zscores(self, df, start_idx: int = 620) -> dict[int, float]:
        """预计算整个 RSRS Z-Score 序列。

        使用固定窗口（600 根 K 线）避免 O(n²) 重复计算。
        返回 {position: z_score} 字典，供信号检测循环直接查询。
        """
        rsrs_window = 600
        zscores: dict[int, float] = {}
        for i in range(start_idx, len(df)):
            window_df = df.iloc[max(0, i - rsrs_window) : i + 1]
            z, _ = self.qe.calculate_rsrs(window_df)
            zscores[i] = z
        return zscores

    def _evaluate_and_cache(
        self, cache_key: str, df, signal_points, hold_len, target_profit, stop_loss
    ) -> dict:
        """评估信号并缓存结果（三策略公共尾声）。"""
        res = self._run_backtest(df, signal_points, hold_len, target_profit, stop_loss)
        if res["total_signals"] > 0:
            with self._lock:
                self._cache[cache_key] = res
            self._save_cache()
        return res

    # ------------------------------------------------------------------
    # 策略回测方法
    # ------------------------------------------------------------------

    def get_strategy_stats(
        self, symbol: str, market: int, category: int, days: int = 250
    ) -> Optional[dict]:
        """
        分周期历史回测。
        - 15m (cat=1): 拉 800 根 ≈ 50 个交易日，约 2.5 个月
        - 30m (cat=2): 拉 600 根 ≈ 75 个交易日，约 3.5 个月
        - 60m (cat=3): 拉 500 根 ≈ 125 个交易日，约 6 个月
        - daily(cat=9): 拉 500 根 ≈ 2 年
        """
        # 各周期独立参数：(拉取深度, MACD窗口, 持仓根数, 信号冷却期)
        param_map = {
            1: {"offset": 4000, "window": 20, "hold": 4, "cool": 6},  # 15m ≈ 1年
            2: {"offset": 2000, "window": 25, "hold": 8, "cool": 10},  # 30m ≈ 1年
            3: {"offset": 1000, "window": 30, "hold": 16, "cool": 20},  # 60m ≈ 1年
            9: {"offset": 750, "window": 30, "hold": 10, "cool": 10},  # daily ≈ 3年
        }
        p = param_map.get(category, param_map[9])

        # 检查缓存：(代码, 周期, 当天日期)
        today_str = datetime.date.today().isoformat()
        cache_key = f"{symbol}_{category}_{today_str}"

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            df = self.qe.fetch_bars(symbol, market, category, offset=p["offset"])
            if df.empty or len(df) < p["window"] * 3:
                return None

            # 独立 copy，防止跨周期指标污染
            df = df.copy()
            df.ta.macd(append=True)

            hold_len = p["hold"]
            cooldown = p["cool"]
            window = p["window"]

            start_scan = window * 2 + 10
            end_scan = len(df) - hold_len - 1

            if end_scan <= start_scan:
                return None

            signal_points = []
            for i in range(start_scan, end_scan):
                if self.qe.check_macd_bullish_divergence(df, window=window, end_idx=i):
                    if not signal_points or (i - signal_points[-1] > cooldown):
                        signal_points.append(i)

            return self._evaluate_and_cache(
                cache_key,
                df,
                signal_points,
                hold_len,
                self.target_profit,
                self.stop_loss,
            )

        except Exception as e:
            app_logger.error(f"回测失败 [{symbol} cat={category}]: {e}")
            return None

    def get_rsrs_strategy_stats(
        self, symbol: str, market: int, category: int = 9, z_threshold: float = 0.7
    ) -> Optional[dict]:
        """
        专门针对 RSRS 指标的择时回测
        - 买入: RSRS Z-Score > z_threshold (通常 0.7)
        - 持有: 默认持仓 10 根 K 线或触及止盈止损
        """
        today_str = datetime.date.today().isoformat()
        cache_key = f"rsrs_{symbol}_{category}_{z_threshold}_{today_str}"

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            # RSRS 需要较深的历史数据进行标准化
            df = self.qe.fetch_bars(symbol, market, category, offset=1200)
            if df.empty or len(df) < 800:
                return None

            df = df.copy()
            hold_len = 10 if category == 9 else 15
            cooldown = 10

            # 预计算整个 RSRS Z-Score 序列（固定窗口 600，避免 O(n²)）
            zscores = self._precompute_rsrs_zscores(df, start_idx=620)

            signal_points = []
            for i in range(620, len(df) - hold_len - 1):
                z = zscores.get(i, 0.0)
                if z > z_threshold:
                    if not signal_points or (i - signal_points[-1] > cooldown):
                        signal_points.append(i)

            return self._evaluate_and_cache(
                cache_key,
                df,
                signal_points,
                hold_len,
                target_profit=0.05,
                stop_loss=0.05,
            )
        except Exception as e:
            app_logger.error(f"RSRS 回测失败 [{symbol}]: {e}")
            return None

    def get_confluence_strategy_stats(
        self, symbol: str, market: int, category: int = 9, z_threshold: float = 0.7
    ) -> Optional[dict]:
        """
        [最强策略] MACD 底背离 + RSRS 走强 共振回测
        """
        today_str = datetime.date.today().isoformat()
        cache_key = f"confluence_{symbol}_{category}_{z_threshold}_{today_str}"

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            # 同样需要较深历史数据
            df = self.qe.fetch_bars(symbol, market, category, offset=1200)
            if df.empty or len(df) < 800:
                return None

            df = df.copy()
            df.ta.macd(append=True)

            hold_len = 10 if category == 9 else 15
            cooldown = 20  # 共振信号更珍贵，冷却期设长一些
            window = 30

            # 预计算整个 RSRS Z-Score 序列（固定窗口 600，避免 O(n²)）
            zscores = self._precompute_rsrs_zscores(df, start_idx=620)

            signal_points = []
            start_idx = 620
            end_idx = len(df) - hold_len - 1

            for i in range(start_idx, end_idx):
                # 因子 1: MACD 底背离
                if self.qe.check_macd_bullish_divergence(df, window=window, end_idx=i):
                    # 因子 2: RSRS 走强 (Z > 0.7) —— 从预计算序列查询
                    z = zscores.get(i, 0.0)

                    if z > z_threshold:
                        if not signal_points or (i - signal_points[-1] > cooldown):
                            signal_points.append(i)

            return self._evaluate_and_cache(
                cache_key,
                df,
                signal_points,
                hold_len,
                target_profit=0.08,
                stop_loss=0.05,
            )
        except Exception as e:
            app_logger.error(f"共振回测失败 [{symbol}]: {e}")
            return None

    def get_score_stats(
        self, symbol: str, market: int, category: int = 9, min_score: int = 3
    ) -> Optional[dict]:
        """
        基于评分的高频表现回测。
        默认回测日线周期下，评分 >= 3 时的表现。
        """
        today_str = datetime.date.today().isoformat()
        cache_key = f"score_{symbol}_{category}_{min_score}_{today_str}"

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            # 增加 offset 以获取更多样本值
            df = self.qe.fetch_bars(symbol, market, category, offset=500)
            if df.empty or len(df) < 100:
                return None

            df = df.copy()
            # 预计算所有指标
            df.ta.macd(append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.ema(length=5, append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=60, append=True)

            hold_len = 5  # 评分信号通常看短线爆发，默认持有5个K线
            cooldown = 10

            signal_points = []
            for i in range(100, len(df) - hold_len - 1):
                # 模拟历史信号：底背离 + OBV
                signals = []
                if self.qe.check_macd_bullish_divergence(df, end_idx=i):
                    signals.append({"name": "MACD底背离"})
                if self.qe.check_accumulation(df, end_idx=i):
                    signals.append({"name": "OBV碎步吸筹"})

                score = self.qe.calculate_intensity_score(df, signals, end_idx=i)
                if score >= min_score:
                    if not signal_points or (i - signal_points[-1] > cooldown):
                        signal_points.append(i)

            n = len(signal_points)
            if n == 0:
                return None

            success_count = 0
            total_profit = 0.0
            for idx in signal_points:
                entry_price = df.loc[idx, "close"]
                if entry_price <= 0:  # 除零防护（T12）
                    continue
                future_df = df.iloc[idx + 1 : idx + 1 + hold_len]
                max_high = future_df["high"].max()
                exit_price = future_df["close"].iloc[-1]

                # 只要持仓期间触及 5% 就算成功
                if (max_high - entry_price) / entry_price >= 0.05:
                    success_count += 1
                    total_profit += 0.05
                else:
                    total_profit += (exit_price - entry_price) / entry_price

            res = {
                "total_signals": n,
                "win_rate": round(success_count / n, 4),
                "avg_profit": round(total_profit / n, 4),
            }
            with self._lock:
                self._cache[cache_key] = res
            self._save_cache()
            return res
        except Exception as e:
            app_logger.error(f"评分回测失败 [{symbol}]: {e}")
            return None

    def _load_cache(self) -> dict:
        """从文件加载缓存并清理过期数据"""
        if not os.path.exists(self._cache_file):
            return {}

        try:
            with open(self._cache_file, encoding="utf-8") as f:
                data = json.load(f)

            # 清理非今日的旧数据
            today_str = datetime.date.today().isoformat()
            new_cache = {k: v for k, v in data.items() if today_str in k}

            if len(new_cache) != len(data):
                # 触发一次异步保存以清理文件
                app_logger.info(
                    f"回测缓存已清理 {len(data) - len(new_cache)} 条过期记录"
                )
                # 这里同步保存一下也没关系，初始化只发生一次
                with open(self._cache_file, "w", encoding="utf-8") as f:
                    json.dump(new_cache, f)

            return new_cache
        except Exception as e:
            app_logger.error(f"加载回测缓存失败: {e}")
            return {}

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        try:
            with self._lock:
                with open(self._cache_file, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f)
        except Exception as e:
            app_logger.error(f"保存回测缓存失败: {e}")
