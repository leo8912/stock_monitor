"""
暗盘资金数据服务
负责后台定时抓取东方财富暗盘数据，提供主界面列的缓存查询和收盘后Excel导出
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from datetime import time as dtime

import requests
from PyQt6 import QtCore

from stock_monitor.utils.logger import app_logger

DARKTRADE_URL = "https://quotederivates.eastmoney.com/datacenter/darktrade"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://emrnweb.eastmoney.com/",
}

# 交易时段边界
_MARKET_START = dtime(9, 15)
_MARKET_END = dtime(15, 5)


def _is_trading_hours() -> bool:
    """是否处于交易时段（含盘前盘后各5分钟缓冲）"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return _MARKET_START <= t <= _MARKET_END


def _get_recent_trade_dates(n: int = 3) -> list[str]:
    """获取最近N个交易日日期列表（简单跳过周末）"""
    dates: list[str] = []
    current = datetime.now()
    while len(dates) < n:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    return dates


def fetch_all_dark_trade(date_str: str | None = None) -> list[dict]:
    """
    抓取全市场暗盘数据（所有股票）
    date_str: 'YYYYMMDD'，默认今天
    返回: list of raw record dict（字段key为字符串数字）
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    all_records: list[dict] = []
    page = 1
    while True:
        params = {
            "version": 100,
            "cver": 100,
            "date": date_str,
            "StartPage": page,
            "NumPerPage": 100,
            "sortflag": 6,  # 按主力流入排序
            "desc": 1,
            "market": "",
            "datetype": "",
        }
        try:
            resp = requests.get(
                DARKTRADE_URL, params=params, headers=_HEADERS, timeout=12
            )
            records: list[dict] = resp.json().get("data", [])
        except Exception as e:
            app_logger.warning(f"[DarkTrade] 抓取第{page}页失败: {e}")
            break

        if not records:
            break
        all_records.extend(records)
        if len(records) < 100:
            break
        page += 1
        if page > 60:
            break

    app_logger.info(f"[DarkTrade] {date_str} 抓取完成，共 {len(all_records)} 条")
    return all_records


def build_net_flow_index(records: list[dict]) -> dict[str, float]:
    """
    将 darktrade 原始记录建立 {stock_code: net_flow_wan} 索引
    net_flow_wan = field[6] / 10000，单位：万元（暗盘主力净流入）
    """
    index: dict[str, float] = {}
    for r in records:
        code = r.get("4", "")
        net_raw = r.get("6", 0)
        if code:
            try:
                index[code] = float(net_raw) / 10000
            except (TypeError, ValueError):
                index[code] = 0.0
    return index


class DarkTradeService(QtCore.QThread):
    """
    暗盘数据后台服务线程

    功能：
    1. 程序启动后立即全量抓取今日暗盘数据（~27秒）
    2. 后台异步抓取前2天历史，计算连续流入/流出天数
    3. 交易时段内每60秒刷新一次缓存
    4. 提供线程安全的 get_dark_flow(code) 查询接口（供主界面列使用）
    5. 收盘后（15:05）触发 close_export_requested 信号，通知导出Excel

    Signals:
        cache_updated: 缓存刷新完成（携带更新时间戳字符串）
        close_export_requested: 收盘后请求导出Excel
    """

    cache_updated = QtCore.pyqtSignal(str)  # 携带 HH:MM 更新时间
    close_export_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._lock = threading.Lock()
        # {stock_code(6位): (net_flow_wan, consecutive_days)}
        self._cache: dict[str, tuple[float, int]] = {}
        self._cache_date: str = ""  # 对应数据的日期
        self._cache_time: str = ""  # 最近更新时间（HH:MM）
        self._fetching = False  # 是否正在抓取（防止重复）
        self._manual_fetch_requested = False  # 手动抓取请求标志
        self._close_exported = False  # 当日收盘是否已导出
        self._close_export_date: str = ""  # 已导出日期，用于次日重置
        self._last_refresh_ts: float = 0.0
        self.refresh_interval: int = 60  # 秒

    # ──────────────────────────────────────────────
    # 公共查询接口（线程安全）
    # ──────────────────────────────────────────────

    def get_dark_flow(self, code: str) -> tuple[float, int] | None:
        """
        查询某只股票当日暗盘净流入（万元）及连续天数
        返回 (net_wan, consecutive_days) 或 None（无数据）
        consecutive_days: 正数=连续流入天数，负数绝对值=连续流出天数
        """
        # 股票代码统一去除市场前缀（sh/sz/hk）
        clean_code = code.lstrip("sShHzZkK") if len(code) > 6 else code
        with self._lock:
            val = self._cache.get(clean_code)
        return val

    def get_cache_time(self) -> str:
        """获取缓存最近更新时间（HH:MM）"""
        with self._lock:
            return self._cache_time

    def has_data(self) -> bool:
        """缓存中是否有数据"""
        with self._lock:
            return bool(self._cache)

    def get_full_cache(self) -> tuple[dict[str, tuple[float, int]], str]:
        """
        获取全量缓存副本（供Excel导出使用）
        返回 ({code: (net_flow_wan, consecutive_days)}, date_str)
        """
        with self._lock:
            return dict(self._cache), self._cache_date

    # ──────────────────────────────────────────────
    # 内部逻辑
    # ──────────────────────────────────────────────

    def _do_fetch_and_update(self, date_str: str | None = None):
        """执行一次全量抓取并更新缓存（仅今天数据，快速）"""
        if self._fetching:
            app_logger.debug("[DarkTrade] 上次抓取未完成，跳过本次")
            return

        self._fetching = True
        try:
            records = fetch_all_dark_trade(date_str)
            if not records:
                return
            new_index = build_net_flow_index(records)
            date_key = date_str or datetime.now().strftime("%Y%m%d")
            update_time = datetime.now().strftime("%H:%M")

            # 先以 consecutive_days=0 更新缓存（保证UI有基本数据）
            with self._lock:
                self._cache = {code: (net, 0) for code, net in new_index.items()}
                self._cache_date = date_key
                self._cache_time = update_time
                self._last_refresh_ts = time.time()

            self.cache_updated.emit(update_time)
            app_logger.info(
                f"[DarkTrade] 今日数据已更新: {len(new_index)} 只股票, 时间={update_time}"
            )
        except Exception as e:
            app_logger.error(f"[DarkTrade] 抓取更新失败: {e}")
        finally:
            self._fetching = False

    def _fetch_history_and_update(self):
        """后台抓取前2天历史数据，计算连续流入/流出天数，更新缓存"""
        try:
            dates = _get_recent_trade_dates(3)  # [今天, 昨天, 前天]
            if len(dates) < 2:
                return

            app_logger.info(f"[DarkTrade] 开始抓取历史数据: {dates[1:]}")

            # 抓取前2天数据
            history: dict[str, dict[str, float]] = {}
            for d in dates[1:]:
                records = fetch_all_dark_trade(d)
                history[d] = build_net_flow_index(records)
                app_logger.info(f"[DarkTrade] {d} 历史: {len(history[d])} 只")

            # 计算连续天数并更新缓存（在锁外构建新缓存，减少锁持有时间）
            update_time = datetime.now().strftime("%H:%M")
            new_cache = {}
            for code, (today_net, _) in self._cache.items():
                # 收集每天的数据（从今天往前）
                all_nets = [today_net]
                for d in dates[1:]:
                    all_nets.append(history.get(d, {}).get(code, 0.0))

                # 计算连续方向天数
                consecutive = 0
                if today_net > 0:
                    # 连续流入：从今天往前，连续正值
                    for v in all_nets:
                        if v > 0:
                            consecutive += 1
                        else:
                            break
                elif today_net < 0:
                    # 连续流出：从今天往前，连续负值（存为负数表示流出）
                    for v in all_nets:
                        if v < 0:
                            consecutive -= 1
                        else:
                            break

                new_cache[code] = (today_net, consecutive)

            with self._lock:
                self._cache = new_cache
                self._cache_time = update_time

            self.cache_updated.emit(update_time)
            app_logger.info(
                f"[DarkTrade] 历史数据已更新，连续天数已计算, 时间={update_time}"
            )
        except Exception as e:
            app_logger.error(f"[DarkTrade] 历史数据抓取失败: {e}")

    def _check_close_export(self):
        """检查是否需要触发收盘导出"""
        now = datetime.now()
        today = now.strftime("%Y%m%d")
        t = now.time()

        # 每日重置
        if self._close_export_date != today:
            self._close_exported = False
            self._close_export_date = today

        # 15:05~15:30 之间触发一次
        if (
            not self._close_exported
            and now.weekday() < 5
            and dtime(15, 5) <= t <= dtime(15, 30)
        ):
            self._close_exported = True
            app_logger.info("[DarkTrade] 触发收盘后Excel导出")
            self.close_export_requested.emit()

    def trigger_manual_fetch(self):
        """手动触发一次全量抓取（供UI按钮调用，线程安全）"""
        app_logger.info("[DarkTrade] 收到手动全量抓取请求")
        self._manual_fetch_requested = True

    def start_service(self):
        """启动服务线程"""
        if not self.isRunning():
            self._running = True
            self.start()

    def stop_service(self):
        """停止服务线程"""
        self._running = False
        self.wait(2000)

    def run(self):
        """线程主循环"""
        app_logger.info_ctx("[DarkTrade] 服务启动", action="start")
        # 启动时立即抓取一次（不限交易时段，确保有数据）
        self._do_fetch_and_update()

        # 启动后异步补历史（不阻塞UI，但计算连续天数后会再次emit）
        self._fetch_history_and_update()

        while self._running:
            try:
                # 处理手动抓取请求（线程安全）
                if self._manual_fetch_requested:
                    self._manual_fetch_requested = False
                    app_logger.info("[DarkTrade] 执行手动全量抓取...")
                    self._do_fetch_and_update()
                    self._fetch_history_and_update()

                self._check_close_export()

                # 交易时段内按间隔刷新
                if _is_trading_hours():
                    elapsed = time.time() - self._last_refresh_ts
                    if elapsed >= self.refresh_interval:
                        self._do_fetch_and_update()

            except Exception as e:
                app_logger.error(f"[DarkTrade] 主循环异常: {e}")

            self.msleep(5000)  # 每5秒检查一次时机

        app_logger.info("[DarkTrade] 服务已停止")


# 全局单例（供 main_window 和其他模块使用）
_dark_trade_service: DarkTradeService | None = None
_dark_trade_service_lock = threading.Lock()


def get_dark_trade_service() -> DarkTradeService:
    """获取全局暗盘服务实例（懒初始化）"""
    global _dark_trade_service
    if _dark_trade_service is None:
        with _dark_trade_service_lock:
            if _dark_trade_service is None:
                _dark_trade_service = DarkTradeService()
    return _dark_trade_service
