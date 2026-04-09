"""
量化分析引擎模块
"""

import os
import sys
import time

import numpy as np
import pandas as pd

try:
    import pandas_ta_classic as ta
except ImportError:
    try:
        import pandas_ta as ta
    except ImportError:
        ta = None
        from stock_monitor.utils.logger import app_logger

        app_logger.warning("pandas_ta 模块缺失，量化扫单指标可能受限。")

from stock_monitor.core.market.market_manager import market_manager
from stock_monitor.core.resolvers.symbol_resolver import SymbolResolver, SymbolType
from stock_monitor.utils.logger import app_logger

from .financial_filter import FinancialFilter

try:
    import akshare as ak
except ImportError:
    ak = None


class LRUCacheWithTTL:
    """LRU + TTL 混合缓存，基于 dict 和 list 实现"""

    def __init__(self, max_size=128, default_ttl=60):
        self.cache = {}
        self.order = []
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    def get(self, key, ttl_override=None):
        if key not in self.cache:
            self.misses += 1
            return None
        entry = self.cache[key]
        value, timestamp, count = entry
        ttl = ttl_override or self.default_ttl
        if time.time() - timestamp > ttl:
            self._remove(key)
            self.misses += 1
            return None
        entry[2] = count + 1
        if key in self.order:
            self.order.remove(key)
        self.order.append(key)
        self.hits += 1
        return value

    def set(self, key, value, ttl_override=None):
        if key in self.cache:
            self._remove(key)
        while len(self.cache) >= self.max_size and self.order:
            self._remove(self.order[0])
        self.cache[key] = [value, time.time(), 0]
        self.order.append(key)

    def delete(self, key):
        """删除缓存中的指定key"""
        self._remove(key)

    def _remove(self, key):
        if key in self.cache:
            del self.cache[key]
        if key in self.order:
            self.order.remove(key)

    def clear(self):
        """清空所有缓存条目"""
        self.cache.clear()
        self.order.clear()

    def get_stats(self):
        total = self.hits + self.misses
        rate = (self.hits / total * 100) if total else 0
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{rate:.1f}%",
            "max_size": self.max_size,
            "avg_ttl": self.default_ttl,
        }


_bars_cache_instance = None


def get_bars_cache(max_size=128, ttl=60):
    global _bars_cache_instance
    if _bars_cache_instance is None:
        _bars_cache_instance = LRUCacheWithTTL(max_size, ttl)
    return _bars_cache_instance


class QuantEngine:
    """量化策略雷达"""

    FreqMap = {"15m": 1, "30m": 2, "60m": 3, "daily": 9}

    TF_CHINESE_MAP = {
        "15m": "15分钟",
        "30m": "30分钟",
        "60m": "60分钟",
        "daily": "日线",
    }

    # 大盘基准缓存，避免重复拉取
    _market_benchmark_cache = {}
    _rsrs_cache = {}  # RSRS 计算缓存：{(symbol, timeframe): (zscore, slope, timestamp)}

    def __init__(self, mootdx_client):
        self.client = mootdx_client
        self._bars_lru_cache = get_bars_cache(max_size=128, ttl=60)
        # 使用带容量限制的LRU缓存，防止长期运行导致内存泄漏
        self._avg_vol_cache = LRUCacheWithTTL(
            max_size=256, default_ttl=86400
        )  # 24小时TTL
        self._auction_cache = LRUCacheWithTTL(max_size=256, default_ttl=300)  # 5分钟TTL
        self._large_order_cache = LRUCacheWithTTL(
            max_size=512, default_ttl=600
        )  # 10分钟TTL
        self.fin_filter = FinancialFilter()

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息（增强版）"""
        stats = {"bars_cache": self._bars_lru_cache.get_stats()}
        # 添加其他缓存统计
        stats["large_order_cache"] = self._large_order_cache.get_stats()
        stats["auction_cache"] = self._auction_cache.get_stats()
        stats["avg_vol_cache"] = self._avg_vol_cache.get_stats()
        return stats

    def _parse_symbol(
        self, symbol: str, market: int = None
    ) -> tuple[str, int, SymbolType]:
        """
        [ELEGANT] 委托 SymbolResolver 解析符号、市场与标的类型
        """
        config = SymbolResolver.resolve(symbol, market)
        return config.code, config.market, config.type

    def _validate_data(self, df: pd.DataFrame, stype: SymbolType) -> bool:
        """
        数据契约验证器：基于标的类型执行相应的一致性检查
        """
        if df is None or df.empty:
            return False

        # 1. 指数类型校验：价格点位不应小于 100 (典型个股价格)
        if stype == SymbolType.INDEX:
            last_price = df.iloc[-1]["close"]
            if last_price < 100:
                app_logger.warning(
                    f"数据契约冲突: 捕获到价格 {last_price}，不满足 INDEX 类型的基准点位要求。"
                )
                return False

        # 2. 通用性日期完整性检查 (可选扩展)
        return True

    def fetch_bars(
        self, symbol: str, market: int = None, category: int = 9, offset: int = 250
    ) -> pd.DataFrame:
        """
        [ELEGANT] 稳健的 K 线获取逻辑，通过 SymbolResolver 自动确定抓取策略
        """
        # 1. 解析初始参数与元数据
        config = SymbolResolver.resolve(symbol, market)
        cache_key = (
            f"{SymbolResolver.get_market_prefix(config.market)}{config.code}",
            category,
        )

        # 2. 检查 LRU 缓存（自动处理 TTL 和淘汰）
        cached_df = self._bars_lru_cache.get(cache_key)
        if cached_df is not None:
            return cached_df

        # 3. 核心抓取循环 (候选路径自动回退)
        # 候选集包含: [首选解析代码] + [解析器提供的备选代码]
        candidate_paths = [(config.code, config.market)] + config.alternates

        final_df = None
        for code_p, market_p in candidate_paths:
            try:
                # 抓取数据 (传入类型标识以触发协议自适应)
                df = self._do_fetch(
                    code_p, market_p, category, offset, stype=config.type
                )

                # 执行数据契约校验
                if self._validate_data(df, config.type):
                    final_df = df
                    break
            except Exception as e:
                # [IMPROVED] 区分不同类型的错误
                error_msg = str(e)
                if "datetime" in error_msg or "time data" in error_msg:
                    # 日期解析错误 - 记录警告但不阻止后续尝试
                    app_logger.warning(f"代码 {code_p} 日期数据异常：{error_msg}")
                else:
                    # 其他错误 - 记录错误
                    app_logger.error(f"代码 {code_p} 数据抓取或解析异常：{e}")
                continue

        if final_df is not None and not final_df.empty:
            # 数据后处理
            final_df = final_df.reset_index(drop=True)

            # [CRITICAL FIX] 立即清洗 datetime 数据，防止后续处理异常
            if "datetime" in final_df.columns:
                final_df = self._clean_datetime_column(final_df)

            if not final_df.empty:
                final_df = final_df.drop_duplicates(subset=["datetime"])
                final_df = final_df.sort_values("datetime", ascending=True).reset_index(
                    drop=True
                )

            # 使用 LRU 缓存（自动淘汰最久未使用的项）
            self._bars_lru_cache.set(cache_key, final_df)
            return final_df

        return pd.DataFrame()

    def _clean_datetime_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗 datetime 列，过滤无效日期数据

        Args:
            df: 包含 datetime 列的 DataFrame

        Returns:
            清洗后的 DataFrame
        """
        try:
            # 先转换为字符串检查格式
            df = df.copy()
            df["datetime"] = df["datetime"].astype(str)

            # 验证日期有效性
            def is_valid_date(date_str):
                """验证日期字符串是否有效"""
                import re

                match = re.match(
                    r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$", str(date_str)
                )
                if not match:
                    return False
                year, month, day, hour, minute = map(int, match.groups())
                # 验证年份范围 (1990-2030)
                if not (1990 <= year <= 2030):
                    return False
                # 验证月份 (1-12)
                if not (1 <= month <= 12):
                    return False
                # 验证日期 (1-31)
                if not (1 <= day <= 31):
                    return False
                # 验证小时 (0-23)
                if not (0 <= hour <= 23):
                    return False
                # 验证分钟 (0-59)
                if not (0 <= minute <= 59):
                    return False
                return True

            # 应用验证过滤
            mask = df["datetime"].apply(is_valid_date)
            filtered_count = (~mask).sum()
            if filtered_count > 0:
                app_logger.debug(f"过滤掉 {filtered_count} 条无效日期数据")

            df = df[mask].copy()

            # 现在安全地转换为 datetime
            if not df.empty:
                df["datetime"] = pd.to_datetime(
                    df["datetime"],
                    format="%Y-%m-%d %H:%M",
                    errors="coerce",  # 无法解析的变为 NaT
                )
                # 删除 NaT 行
                df = df.dropna(subset=["datetime"])

        except Exception as e:
            app_logger.warning(f"datetime 列清洗异常：{e}，将保留原始数据")

        return df

    def _safe_fetch_chunk(
        self,
        api_method,
        symbol: str,
        market: int,
        category: int,
        start: int,
        offset: int,
    ) -> pd.DataFrame:
        """
        拉取单个 K 线分片，并在日期解析异常时返回空表而不是打断整次抓取。
        """
        try:
            return api_method(
                symbol=symbol,
                market=market,
                category=category,
                start=start,
                offset=offset,
            )
        except Exception as e:
            error_msg = str(e)
            if "datetime" in error_msg or "time data" in error_msg:
                app_logger.warning(
                    f"K线分片日期异常 [{symbol} cat={category} start={start} offset={offset}]: {error_msg}"
                )
                return pd.DataFrame()
            raise

    def _do_fetch(
        self,
        symbol: str,
        market: int,
        category: int,
        offset: int,
        stype: SymbolType = SymbolType.STOCK,
    ) -> pd.DataFrame:
        """
        执行底层数据抓取，支持协议自适应 (INDEX 专用接口)
        """
        # [ELEGANT] 针对指数类型，使用专用的 index 接口，避开 bars 接口的二进制解析 bug
        api_method = (
            self.client.index if stype == SymbolType.INDEX else self.client.bars
        )

        if offset <= 800:
            return self._safe_fetch_chunk(
                api_method,
                symbol=symbol,
                market=market,
                category=category,
                start=0,
                offset=offset,
            )
        else:
            chunks = []
            for start in range(0, offset, 800):
                current_offset = min(800, offset - start)
                chunk = self._safe_fetch_chunk(
                    api_method,
                    symbol=symbol,
                    market=market,
                    category=category,
                    start=start,
                    offset=current_offset,
                )
                if chunk is not None and not chunk.empty:
                    chunks.append(chunk)
                else:
                    break
            return pd.concat(chunks) if chunks else pd.DataFrame()

    def check_macd_bullish_divergence(
        self, df: pd.DataFrame, window: int = 30, end_idx: int = None
    ) -> bool:
        try:
            if "MACDh_12_26_9" not in df.columns:
                df.ta.macd(append=True)
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < window * 2:
                return False
            cols = [c for c in df.columns if c.startswith("MACDh_")]
            if not cols:
                return False
            m_col = cols[0]
            recent = curr.iloc[-window:]
            prev = curr.iloc[-window * 2 : -window]
            ri = recent["close"].idxmin()
            pi = prev["close"].idxmin()
            if (
                recent.loc[ri, "close"] < prev.loc[pi, "close"]
                and recent.loc[ri, m_col] > prev.loc[pi, m_col]
            ):
                if ri >= curr.index[-5]:
                    return True
            return False
        except Exception:
            return False

    def check_bbands_squeeze(self, df: pd.DataFrame, end_idx: int = None) -> bool:
        try:
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < 100:
                return False
            cols = [c for c in curr.columns if c.startswith("BBB_")]
            if not cols:
                return False
            bw = curr[cols[0]].iloc[-1]
            return bw <= curr[cols[0]].iloc[-100:].min() * 1.05
        except Exception:
            return False

    def calculate_rsrs(
        self, df: pd.DataFrame, n: int = 18, m: int = 600
    ) -> tuple[float, float]:
        """
        计算 RSRS (阻力支撑相对强度) 指标
        返回: (zscore, slope)
        """
        try:
            data_len = len(df)

            # 渐进式降级策略
            if data_len < n + m:
                min_required = n + max(60, m // 4)

                if data_len < min_required:
                    app_logger.debug(f"RSRS 数据不足：{data_len} < {min_required}")
                    return 0.0, 0.0

                adjusted_m = min(m, data_len - n)
                app_logger.info(f"RSRS 降级模式：m={m}->{adjusted_m}")
                return self.calculate_rsrs(df, n=n, m=adjusted_m)

                return 0.0, 0.0

            # 1. 计算斜率序列 (Slope)
            # 为了性能，只计算最近 M+1 个斜率用于标准化
            slopes = []
            highs = df["high"].values
            lows = df["low"].values

            # 使用 rolling window 计算斜率
            for i in range(len(df) - m, len(df)):
                y = highs[i - n + 1 : i + 1]
                x = lows[i - n + 1 : i + 1]
                slope = np.polyfit(x, y, 1)[0]
                slopes.append(slope)

            # 2. 标准化 (Z-Score)
            curr_slope = slopes[-1]
            history_slopes = np.array(slopes)
            mean_s = np.mean(history_slopes)
            std_s = np.std(history_slopes)

            zscore = (curr_slope - mean_s) / std_s if std_s != 0 else 0
            return round(zscore, 3), round(curr_slope, 3)
        except Exception as e:
            app_logger.warning(f"RSRS 计算失败: {e}")
            return 0.0, 0.0

    def detect_obv_accumulation(self, symbol: str, df: pd.DataFrame) -> list:
        """
        [NEW] OBV 低位吸筹检测入口，保持与 QuantWorker 兼容
        """
        if self.check_accumulation(df):
            # 获取最近一根 K 线的时间
            last_time = df.iloc[-1]["datetime"] if not df.empty else ""
            return [{"level": "日线", "time": last_time}]
        return []

    def check_accumulation(self, df: pd.DataFrame, end_idx: int = None) -> bool:
        try:
            if "OBV" not in df.columns:
                df.ta.obv(append=True)
            curr = df if end_idx is None else df.iloc[: end_idx + 1]
            if len(curr) < 20:
                return False
            r20 = curr.iloc[-20:]
            vty = (r20["high"].max() - r20["low"].min()) / (r20["low"].min() + 1e-9)
            if vty < 0.10:
                return r20["OBV"].rolling(5).mean().iloc[-1] > r20["OBV"].mean() * 1.05
            return False
        except Exception:
            return False

    def get_bbands_position_desc(self, df: pd.DataFrame) -> str:
        """价格相对于布林带的位置，用 emoji 简洁标注"""
        try:
            # 使用浅拷贝减少内存分配（只读场景无需深拷贝）
            tmp = df.copy(deep=False)
            tmp.ta.bbands(length=20, std=2, append=True)
            bbl = [c for c in tmp.columns if c.startswith("BBL_")]
            bbu = [c for c in tmp.columns if c.startswith("BBU_")]
            bbb = [c for c in tmp.columns if c.startswith("BBB_")]
            if not bbl or not bbu:
                return " 🟡 中位震荡"
            c = tmp["close"].iloc[-1]
            lower_band = tmp[bbl[0]].iloc[-1]
            upper_band = tmp[bbu[0]].iloc[-1]
            is_sq = (
                len(tmp) >= 100
                and bbb
                and tmp[bbb[0]].iloc[-1] <= tmp[bbb[0]].iloc[-100:].min() * 1.05
            )
            sq = "-变盘" if is_sq else ""
            if c <= lower_band * 1.008:
                return f" 🟢 下轨支撑{sq}"
            elif c >= upper_band * 0.992:
                return f" 🔴 上轨阻力{sq}"
            else:
                return f" 🟡 中位震荡{sq}"
        except Exception:
            return ""

    def calculate_comprehensive_indicators(self, df: pd.DataFrame) -> dict:
        """计算核心技术指标并返回易读的汇总，用于微信推送描述"""
        if df.empty or len(df) < 60:
            return {}
        try:
            res = {}
            # 1. 均线分析 (EMA5, 10, 20, 60)
            df.ta.ema(length=5, append=True)
            df.ta.ema(length=10, append=True)
            df.ta.ema(length=20, append=True)
            df.ta.ema(length=60, append=True)

            c = df["close"].iloc[-1]
            e5, e10, e20, e60 = (
                df["EMA_5"].iloc[-1],
                df["EMA_10"].iloc[-1],
                df["EMA_20"].iloc[-1],
                df["EMA_60"].iloc[-1],
            )

            # 判断大趋势
            if c > e20 > e60:
                res["trend"] = "🔴 多头"
            elif c < e20 < e60:
                res["trend"] = "🟢 空头"
            else:
                res["trend"] = "🟡 震荡"

            # 压力支撑位提示
            if c > e5 > e10:
                res["support"] = f"EMA5 ({e5:.2f})"
            elif c < e5:
                res["resistance"] = f"EMA5 ({e5:.2f})"

            # 2. RSI 分析
            df.ta.rsi(length=14, append=True)
            rsi = df["RSI_14"].iloc[-1]
            if rsi > 70:
                res["strength"] = "🔥 极强/超买"
            elif rsi < 30:
                res["strength"] = "❄️ 极弱/超卖"
            else:
                res["strength"] = f"⚡ 强弱度:{rsi:.0f}"

            # 3. 成交量脉冲 (Volume Pulse)
            vol_avg20 = df["volume"].rolling(20).mean().iloc[-1]
            vol_curr = df["volume"].iloc[-1]
            if vol_curr > vol_avg20 * 2.0:
                res["pulse"] = f"🚀 异常放量 (x{vol_curr / vol_avg20:.1f})"

            return res
        except Exception as e:
            app_logger.warning(f"指标计算异常: {e}")
            return {}

    def get_market_relative_strength(self) -> float:
        """获取个股相对于大盘的强弱。当前取上证指数 (sh000001) 同比涨跌幅。"""
        try:
            idx_symbol = "000001"
            idx_market = 1  # SH

            # 检查基准缓存 (1分钟有效期)
            import time

            now_ts = time.time()
            if "benchmark" in self._market_benchmark_cache:
                cache_val, ts = self._market_benchmark_cache["benchmark"]
                if now_ts - ts < 60:
                    return cache_val

            idx_info = self.get_latest_price_info(idx_symbol, idx_market)
            idx_pct = idx_info.get("pct", 0.0)
            self._market_benchmark_cache["benchmark"] = (idx_pct, now_ts)
            return idx_pct
        except Exception:
            return 0.0

    def calculate_intensity_score(
        self, df: pd.DataFrame, signals: list[dict], end_idx: int = None
    ) -> int:
        """
        根据信号组合与技术面状态，计算利好/利空得分 [-5, 5]
        """
        if df.empty:
            return 0

        curr = df if end_idx is None else df.iloc[: end_idx + 1]
        if len(curr) < 20:
            return 0

        score = 0
        signal_names = [s["name"] for s in signals]

        # 1. 核心信号权重
        if "MACD底背离" in signal_names:
            score += 3
        if "OBV碎步吸筹" in signal_names:
            score += 2

        # 2. 辅助技术面验证
        try:
            # 提高性能：如果列已经存在则不再重新计算整个 series
            if "RSI_14" not in df.columns:
                df.ta.rsi(length=14, append=True)
            if "EMA_5" not in df.columns:
                df.ta.ema(length=5, append=True)
            if "EMA_20" not in df.columns:
                df.ta.ema(length=20, append=True)
            if "EMA_60" not in df.columns:
                df.ta.ema(length=60, append=True)

            rsi = (
                df["RSI_14"].iloc[end_idx]
                if end_idx is not None
                else df["RSI_14"].iloc[-1]
            )
            if rsi < 30:
                score += 1  # 超卖区增加反弹概率
            elif rsi > 70:
                score -= 1  # 超买区风险

            # 均线多头排列验证 (EMA5 > 10 > 20 > 60)
            c = curr["close"].iloc[-1]
            e5 = (
                df["EMA_5"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_5"].iloc[-1]
            )
            e20 = (
                df["EMA_20"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_20"].iloc[-1]
            )
            e60 = (
                df["EMA_60"].iloc[end_idx]
                if end_idx is not None
                else df["EMA_60"].iloc[-1]
            )

            if c > e5 > e20 > e60:
                score += 1
            elif c < e5 < e20 < e60:
                score -= 3  # 极弱势

            # 3. RSRS 评分
            z, s = self.calculate_rsrs(curr)
            if z > 0.7:
                score += 1
            elif z < -0.7:
                score -= 1
        except Exception:
            pass

        # 限制范围在 [-5, 5]
        return max(-5, min(5, score))

    def calculate_market_sentiment_factor(self) -> tuple[float, str]:
        """
        计算市场环境因子评分 [-3, 1.5]
        """
        sentiment = market_manager.get_sentiment()
        up_ratio = sentiment.up_ratio

        # 优化为更平稳且梯度鲜明的反馈
        if up_ratio > 0.8:
            return 1.5, "🔥 极佳/普涨牛市"
        if up_ratio > 0.6:
            return 1.0, "🔴 偏强/赚钱效应好"
        if up_ratio > 0.4:
            return 0.0, "🟡 中性/存量博弈"
        if up_ratio > 0.2:
            return -1.5, "🟢 偏弱/亏钱效应"
        return -3.0, "❄️ 极弱/恐慌普跌"

    def calculate_intensity_score_with_symbol(
        self, symbol: str, df: pd.DataFrame, signals: list[dict]
    ) -> tuple[int, dict]:
        """
        扩展版评分逻辑：支持传入 symbol 进行综合审计（财务、资金、环境）
        返回: (最终总分, 审计详情字典)
        """
        base_score = self.calculate_intensity_score(df, signals)

        # 1. 环境因子 (Market Sentiment)
        m_factor, m_desc = self.calculate_market_sentiment_factor()

        # 2. 资金流因子 (Money Flow)
        buy, sell, net = self.fetch_large_orders_flow(symbol)
        flow_factor = 0
        if buy + sell > 0:
            ratio = net / (buy + sell)
            if ratio > 0.15:
                flow_factor = 1.0  # 净流入显著
            elif ratio < -0.15:
                flow_factor = -1.5  # 净流出显著

        # 3. 财务审计 (Fundamental)
        audit = self.fin_filter.get_financial_audit(symbol)

        # 4. 综合总分计算
        # 总分 = 技术得分 + 环境因子 + 资金因子 + 财务偏移
        final_score = base_score + m_factor + flow_factor + audit.get("score_offset", 0)

        # 5. 核心风控熔断逻辑
        # 财务风险等级：红色禁止评分超过0
        if audit.get("rating") == "🔴":
            final_score = min(0, final_score)

        # 市场系统性风险：强制不发出强力买入建议 (超过0分)
        if m_factor <= -3.0:
            final_score = min(-1.0, final_score)

        audit["market_sentiment"] = {"factor": m_factor, "desc": m_desc}
        audit["money_flow"] = {
            "buy": buy,
            "sell": sell,
            "net": net,
            "factor": flow_factor,
        }

        return int(max(-5, min(5, final_score))), audit

    def get_latest_price_info(self, symbol: str, market: int = None) -> dict:
        """获取最新价格和涨跌幅（从日线K线计算）"""
        try:
            df = self.fetch_bars(symbol, market, category=9, offset=3)
            if df.empty or len(df) < 2:
                return {}
            now = df.iloc[-1]["close"]
            prev = df.iloc[-2]["close"]
            pct = ((now - prev) / prev * 100) if prev != 0 else 0
            return {"price": now, "pct": pct}
        except Exception:
            return {}

    def _ensure_ta_active(self, df: pd.DataFrame):
        """确保 pandas-ta 访问器已激活 (针对打包环境的自愈逻辑)"""
        # 如果已经激活，直接返回
        if hasattr(pd.DataFrame, "ta"):
            return True

        try:
            # 1. 尝试常规导入 (兼容 classic 和标准版)
            try:
                import pandas_ta_classic as _ta  # noqa: F401
            except ImportError:
                try:
                    import pandas_ta as _ta  # noqa: F401
                except ImportError:
                    pass

            if hasattr(pd.DataFrame, "ta"):
                return True

            # 2. 运行时强制补丁 (Runtime Patch) - 针对 Frozen 环境
            if getattr(sys, "frozen", False):
                base_path = sys._MEIPASS
                internal_base = os.path.join(base_path, "_internal")
                if internal_base not in sys.path:
                    sys.path.insert(0, internal_base)

            # 尝试再次导入并手动注册
            try:
                try:
                    import pandas_ta_classic as _pta  # noqa: F401
                except ImportError:
                    import pandas_ta as _pta  # noqa: F401

                if not hasattr(pd.DataFrame, "ta"):
                    # 强行调用其内部类进行注册
                    from pandas_ta.core import AnalysisIndicators

                    pd.api.extensions.register_dataframe_accessor("ta")(
                        AnalysisIndicators
                    )
                self.logger.info("已通过代码手动激活 pandas-ta 访问器。")
                return True
            except (ImportError, ModuleNotFoundError) as e:
                self.logger.warning(f"无法激活 pandas-ta 访问器: {str(e)}")
                return False
        except Exception as e:
            import traceback

            self.logger.warning(
                f"激活 pandas-ta 时发生未知错误: {e}\n{traceback.format_exc()}"
            )
            return False
        return True

    def scan_all_timeframes(self, symbol: str, market: int = None) -> list[dict]:
        """全量扫描，按大周期→小周期排序返回"""
        # 针对打包环境的自愈点
        self._ensure_ta_active(pd.DataFrame())

        results = []
        for tf, cat in self.FreqMap.items():
            try:
                df = self.fetch_bars(symbol, market, cat, offset=250)
                if df.empty or len(df) < 50:
                    continue
                df.ta.macd(append=True)
                pos = self.get_bbands_position_desc(df)
                if self.check_macd_bullish_divergence(df):
                    results.append(
                        {"tf": tf, "category": cat, "name": "MACD底背离", "desc": pos}
                    )
                if cat in (3, 9) and self.check_accumulation(df):
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "OBV碎步吸筹",
                            "desc": f"(主力蓄势){pos}",
                        }
                    )

                # 3. RSRS 择时信号
                z, _ = self.calculate_rsrs(df)
                if z > 1.0:
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "RSRS极强",
                            "desc": f"阻力极小(Z:{z})",
                        }
                    )
                elif z > 0.7:
                    results.append(
                        {
                            "tf": tf,
                            "category": cat,
                            "name": "RSRS走强",
                            "desc": f"突破压力(Z:{z})",
                        }
                    )
            except Exception as e:
                app_logger.error(f"周期 {tf} 扫描异常 [{symbol}]: {e}")

        # 按大周期到小周期排序：daily > 60m > 30m > 15m
        order = {"daily": 0, "60m": 1, "30m": 2, "15m": 3}
        return sorted(results, key=lambda x: order.get(x["tf"], 9))

    def _find_subsequence(self, full_seq: list, sub_seq: list) -> int:
        """
        在 full_seq 中反向查找 sub_seq，返回 sub_seq 结束位置的索引。
        即返回 full_seq 中全新数据的起始偏移量。
        如果没找到，返回 -1。
        """
        if not sub_seq:
            return 0
        n = len(full_seq)
        m = len(sub_seq)
        if m > n:
            return -1
        # 从后往前匹配（增量数据在最后）
        for i in range(n - m, -1, -1):
            if full_seq[i : i + m] == sub_seq:
                return i + m
        return -1

    def _get_adaptive_order_threshold(self, symbol: str) -> int:
        """根据股票市值自适应获取大单阈值

        Args:
            symbol (str): 股票代码（带市场前缀）

        Returns:
            int: 大单金额阈值（元）

        阈值分档：
        - 小盘股 (<100 亿): 20 万元
        - 中盘股 (100-1000 亿): 50 万元
        - 大盘股 (>1000 亿): 100 万元
        """
        try:
            import akshare as ak

            _ = symbol[2:] if symbol.startswith(("sh", "sz")) else symbol
            df = ak.stock_individual_info(symbol=symbol)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    if "总市值" in str(row.get("item", "")):
                        market_cap_str = str(row.get("value", "0")).replace(",", "")
                        try:
                            market_cap = float(market_cap_str)
                            from .quant_engine_constants import (
                                BIG_ORDER_THRESHOLD_LARGE_CAP,
                                BIG_ORDER_THRESHOLD_MID_CAP,
                                BIG_ORDER_THRESHOLD_SMALL_CAP,
                                MARKET_CAP_MID_LIMIT,
                                MARKET_CAP_SMALL_LIMIT,
                            )

                            if market_cap < MARKET_CAP_SMALL_LIMIT:
                                return BIG_ORDER_THRESHOLD_SMALL_CAP
                            elif market_cap < MARKET_CAP_MID_LIMIT:
                                return BIG_ORDER_THRESHOLD_MID_CAP
                            else:
                                return BIG_ORDER_THRESHOLD_LARGE_CAP
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        from .quant_engine_constants import BIG_ORDER_THRESHOLD_AMOUNT

        return BIG_ORDER_THRESHOLD_AMOUNT

    def fetch_large_orders_flow(self, code: str) -> tuple[float, float, float]:
        """
        获取单只股票从当日开盘起的所有主动大单买入/卖出量 (单位：手)
        过滤条件：仅统计单笔 >= 100手的成交记录。
        """
        if self.client is None:
            return (0.0, 0.0, 0.0)

        try:
            if not code.startswith(("sh", "sz")):
                return (0.0, 0.0, 0.0)

            market = 1 if code.startswith("sh") else 0
            pure_code = code[2:]
            today = time.strftime("%Y-%m-%d")

            # 初始化或重置日期缓存（每天开盘清零）
            is_first_fetch = False
            cache = self._large_order_cache.get(code)
            if cache is None or cache.get("last_date") != today:
                cache = {
                    "last_tail": [],  # 上次处理结果的末尾 N 条记录（用于精确匹配增量）
                    "buy_vol": 0.0,
                    "sell_vol": 0.0,
                    "last_date": today,
                }
                self._large_order_cache.set(code, cache)
                is_first_fetch = True

            BATCH_SIZE = 2000

            if is_first_fetch:
                # ====== 首次拉取：循环获取全量当日数据 ======
                dfs = []
                offset = 0
                max_reach = 1000000  # 安全熔断：100万笔

                while True:
                    df = self.client.transaction(
                        symbol=pure_code, market=market, start=offset, count=BATCH_SIZE
                    )
                    if df is None or df.empty:
                        break

                    actual_count = len(df)
                    dfs.append(df)

                    # 检查该 batch 中最老记录的时间（TDX 是倒序排列的）
                    oldest_time = df.iloc[-1]["time"]

                    if oldest_time <= "09:25":
                        app_logger.debug(
                            f"{code} 已回溯至开盘时刻或更早 ({oldest_time})，停止抓取。"
                        )
                        break

                    if actual_count < BATCH_SIZE:
                        break

                    offset += actual_count
                    if offset >= max_reach:
                        app_logger.warning(f"{code} 达到百万笔回溯上限，强制停止。")
                        break

                if not dfs:
                    app_logger.debug(f"{code} 首次大单获取从 TDX 无结果，尝试补偿")
                    # 即使 TDX 没结果，也要尝试盘后补全逻辑
                    buy, sell = cache.get("buy_vol", 0.0), cache.get("sell_vol", 0.0)
                    return (buy, sell, buy - sell)

                full_df = pd.concat(dfs[::-1], ignore_index=True)

                # 统计所有大单 (从 09:25 集合竞价成交开始统计)
                full_df = full_df[full_df["time"] >= "09:25"]
                full_df["amount"] = full_df["price"] * full_df["vol"] * 100
                threshold = self._get_adaptive_order_threshold(code)
                big_orders = full_df[full_df["amount"] >= threshold]
                if not big_orders.empty:
                    cache["buy_vol"] = float(
                        big_orders[big_orders["buyorsell"] == 0]["amount"].sum()
                    )
                    cache["sell_vol"] = float(
                        big_orders[big_orders["buyorsell"] == 1]["amount"].sum()
                    )

                # 记录最后 10 条的指纹
                tail_records = (
                    full_df[["time", "vol", "buyorsell"]].tail(10).values.tolist()
                )
                cache["last_tail"] = tail_records

                app_logger.debug(
                    f"{code} 首次大单总条数{len(full_df)}，买{cache['buy_vol']:.0f}卖{cache['sell_vol']:.0f}"
                )

                # [DONE] 统一通过私有方法处理补偿判定

            else:
                # ====== 增量拉取：只请求最新 batch，倒序匹配 ======
                df = self.client.transaction(
                    symbol=pure_code, market=market, start=0, count=BATCH_SIZE
                )

                if df is None or df.empty:
                    return (
                        cache["buy_vol"],
                        cache["sell_vol"],
                        cache["buy_vol"] - cache["sell_vol"],
                    )

                new_records = df[["time", "vol", "buyorsell"]].values.tolist()
                last_tail = cache["last_tail"]

                start_idx = self._find_subsequence(new_records, last_tail)

                if start_idx == -1:
                    app_logger.warning(
                        f"{code} 增量匹配失败(指纹断层)，重置缓存下回合拉全量"
                    )
                    self._large_order_cache.delete(code)
                    return (
                        cache["buy_vol"],
                        cache["sell_vol"],
                        cache["buy_vol"] - cache["sell_vol"],
                    )

                new_added_df = df.iloc[start_idx + len(last_tail) :]

                if not new_added_df.empty:
                    new_added_df = new_added_df.copy()
                    new_added_df = new_added_df[new_added_df["time"] >= "09:25"]
                    new_added_df["amount"] = (
                        new_added_df["price"] * new_added_df["vol"] * 100
                    )
                    threshold = self._get_adaptive_order_threshold(code)
                    big_orders = new_added_df[new_added_df["amount"] >= threshold]
                    if not big_orders.empty:
                        cache["buy_vol"] += float(
                            big_orders[big_orders["buyorsell"] == 0]["amount"].sum()
                        )
                        cache["sell_vol"] += float(
                            big_orders[big_orders["buyorsell"] == 1]["amount"].sum()
                        )

                    cache["last_tail"] = (
                        df[["time", "vol", "buyorsell"]].tail(10).values.tolist()
                    )

            # 返回全天累计大单买、卖及净流入
            accumulated_net = cache["buy_vol"] - cache["sell_vol"]
            return (cache["buy_vol"], cache["sell_vol"], accumulated_net)

        except Exception as e:
            app_logger.warning(f"获取 {code} 全量大单数据失败: {e}")
            cached = self._large_order_cache.get(code)
            if cached:
                buy, sell = cached.get("buy_vol", 0.0), cached.get("sell_vol", 0.0)
            else:
                buy, sell = 0.0, 0.0
            return (buy, sell, buy - sell)

    def _fetch_ak_fallback_money_flow(
        self, pure_code, market, cache, full_df: pd.DataFrame = None
    ):
        """
        [ELEGANT] 资金流向补全逻辑：针对 TDX 接口局限性，在收盘后或开启时补全当日主力资金数据
        """
        earliest_time = (
            full_df.iloc[0]["time"]
            if (full_df is not None and len(full_df) > 0)
            else "23:59"
        )
        from datetime import datetime

        curr_hour = datetime.now().hour
        # 如果当前已过 15:00 (或 09:00 前开机)，且拉取到的最早记录晚于 09:35 (说明回溯失败)
        if (curr_hour >= 15 or curr_hour < 9) and earliest_time > "09:35":
            if not ak:
                app_logger.warning("akshare 未安装，无法执行盘后补偿。")
                return

            code_with_market = f"{'sh' if market == 1 else 'sz'}{pure_code}"
            try:
                app_logger.info(
                    f"{code_with_market} 触发盘后资金补偿 (TDX仅回溯至 {earliest_time})"
                )
                flow_df = ak.stock_individual_fund_flow(
                    stock=pure_code, market="sh" if market == 1 else "sz"
                )
                if flow_df is not None and not flow_df.empty:
                    last_row = flow_df.iloc[-1]
                    net_main = float(last_row["主力净流入-净额"])
                    # 对重分配：仅为了保证 net = buy - sell
                    if net_main > 0:
                        cache["buy_vol"] = net_main
                        cache["sell_vol"] = 0.0
                    else:
                        cache["buy_vol"] = 0.0
                        cache["sell_vol"] = abs(net_main)
                    app_logger.info(
                        f"{code_with_market} 补偿成功：主力净流入 {net_main:.0f}"
                    )
            except Exception as e:
                app_logger.warning(
                    f"akshare 资金流向补偿失败 [{code_with_market}]: {e}"
                )

    def get_five_day_avg_minute_volume(self, code: str) -> float:
        """获取前 5 日平均每分钟成交额 (不含今日)"""
        today = time.strftime("%Y-%m-%d")

        # 检查缓存
        cached_entry = self._avg_vol_cache.get(code)
        if (
            cached_entry
            and isinstance(cached_entry, dict)
            and cached_entry.get("date") == today
        ):
            return cached_entry.get("value", 1000000.0)

        try:
            market = 1 if code.startswith("sh") else 0
            pure_code = code[2:]
            # 类别 4 为日线，获取 6 根以防万一
            df = self.client.bars(symbol=pure_code, market=market, category=4, count=6)
            if df is not None and len(df) >= 2:
                last_dt = str(df.iloc[-1].name)
                # 兼容不同格式的 datetime index
                if today in last_dt:
                    hist_df = df.iloc[:-1].tail(5)
                else:
                    hist_df = df.tail(5)

                if not hist_df.empty:
                    # A股每日交易 240 分钟
                    avg_daily_amount = hist_df["amount"].mean()
                    avg_minute_amount = avg_daily_amount / 240.0
                    # 保存到LRU缓存
                    self._avg_vol_cache.set(
                        code,
                        {
                            "date": today,
                            "value": avg_minute_amount,
                        },
                    )
                    return avg_minute_amount
        except Exception as e:
            app_logger.warning(f"获取 {code} 5日均量失败: {e}")

        return 1000000.0  # 保底 100 万，防止指标虚高

    def fetch_call_auction_data(self, code: str) -> dict:
        """
        获取集合竞价分析数据
        返回: {price, volume, intensity, pct}
        """
        if self.client is None:
            return {}

        now_hm = time.strftime("%H:%M")
        # 仅在开盘前或开盘初期的特定时段有效 (09:15-09:35)
        # 或者在盘后为了回溯展示
        if not ("09:15" <= now_hm <= "15:10"):  # 稍微放宽一点用于测试
            cached = self._auction_cache.get(code)
            return cached if cached else {}

        # 核心逻辑：如果在 09:15-09:25，获取实时行情；如果已过 09:25，获取 09:25 的成交数据
        try:
            market = 1 if code.startswith("sh") else 0
            pure_code = code[2:]

            # 1. 获取当前行情（或者最后一次行情预估）
            # [STABLE] 使用完整 code (带前缀) 避免歧义
            q_df = self.client.quotes(symbol=[code])
            if q_df is None or q_df.empty:
                return {}

            current_price = float(q_df.iloc[0]["price"])
            last_close = float(q_df.iloc[0]["last_close"])
            pct = (current_price / last_close - 1) * 100 if last_close > 0 else 0.0

            auction_vol = 0.0
            intensity = 0.0

            if "09:15" <= now_hm < "09:25":
                # 实时的虚拟竞价 (Virtual Auction)
                # 使用买一量 * 价格作为金额 (Sina/TDX 竞价期间 bid_vol1 为匹配量)
                auction_vol = float(q_df.iloc[0]["bid_vol1"] * current_price * 100)
            else:
                # 已过 09:25 或盘后，抓取 09:25:00 这一笔真实成交
                df = self.client.transaction(
                    symbol=pure_code, market=market, start=0, count=100
                )
                if df is not None and not df.empty:
                    auction_rows = df[df["time"] <= "09:25"]
                    if not auction_rows.empty:
                        trade = auction_rows.iloc[-1]
                        auction_vol = float(trade["price"] * trade["vol"] * 100)

            # 2. 计算强度
            if auction_vol > 0:
                avg_min_vol = self.get_five_day_avg_minute_volume(code)
                intensity = auction_vol / avg_min_vol
                app_logger.debug(
                    f"[竞价分析] {code} 强度:{intensity:.1f}x, 金额:{auction_vol/10000:.0f}万"
                )

            res = {
                "price": current_price,
                "volume": auction_vol,
                "intensity": intensity,
                "pct": pct,
            }
            self._auction_cache.set(code, res)
            return res

        except Exception as e:
            app_logger.warning(f"获取 {code} 竞价数据失败: {e}")
            cached = self._auction_cache.get(code)
            return cached if cached else {}
