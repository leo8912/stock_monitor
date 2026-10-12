from typing import Any

from PyQt6 import QtCore

from stock_monitor.core.market.market_manager import market_manager
from stock_monitor.core.market.stock_manager import stock_manager
from stock_monitor.core.workers.base import BaseWorker
from stock_monitor.utils.logger import app_logger


class MarketStatsWorker(BaseWorker):
    """全市场统计工作线程"""

    # 信号：上涨数，下跌数，平盘数，总数
    stats_updated = QtCore.pyqtSignal(int, int, int, int)

    def run(self):
        """线程执行入口"""
        # 初始延迟
        self.msleep(2000)

        while self._is_running:
            try:
                # 检查市场是否开市（仅用于状态日志，刷新间隔不随开闭市变化）
                market_open = market_manager.is_market_open()
                app_logger.info(
                    f"[市场统计] 市场状态检查：{'开市' if market_open else '闭市'}"
                )

                app_logger.info("[市场统计] 开始获取全市场数据...")
                market_data = stock_manager.get_all_market_data()

                if market_data:
                    app_logger.info(
                        f"[市场统计] 成功获取数据，共 {len(market_data)} 只股票"
                    )
                    stats = self._calculate_stats(market_data)
                    app_logger.info(
                        f"[市场统计] 统计结果：上涨={stats['up_count']}, 下跌={stats['down_count']}, 平盘={stats['flat_count']}, 总计={stats['total_count']}"
                    )
                    self.stats_updated.emit(
                        stats["up_count"],
                        stats["down_count"],
                        stats["flat_count"],
                        stats["total_count"],
                    )
                    # 同步到全局管理器
                    market_manager.update_sentiment(
                        stats["up_count"],
                        stats["down_count"],
                        stats["flat_count"],
                        stats["total_count"],
                    )
                    app_logger.info("[市场统计] 已同步情绪数据到管理器")
                else:
                    app_logger.warning("[市场统计] 获取全市场数据失败，返回 None")

                # 休眠
                for _ in range(self.interval):
                    if not self._is_running:
                        break
                    self.sleep(1)

            except Exception as e:
                app_logger.error(f"市场统计线程异常：{e}", exc_info=True)
                # 分片睡眠：异常退避期间仍能及时响应停止请求
                for _ in range(10):
                    if not self._is_running:
                        break
                    self.sleep(1)

    def _calculate_stats(self, data: dict[str, Any]) -> dict[str, int]:
        """计算市场统计数据"""
        up = 0
        down = 0
        flat = 0
        total = 0

        for _code, info in data.items():
            if not isinstance(info, dict):
                continue

            name = info.get("name", "")
            # 跳过指数类聚合行
            if "指数" in name or "A股" in name:
                continue

            try:
                close = float(info.get("close", 0))
                now = float(info.get("now", 0))

                # 当前价为 0（如集合竞价尚未产生成交）无法判定涨跌，跳过统计，
                # 避免误判为下跌；昨收缺失（新股/数据异常）口径一致，不计平盘
                if now <= 0 or close <= 0:
                    continue

                if now > close:
                    up += 1
                elif now < close:
                    down += 1
                else:
                    flat += 1

                total += 1
            except (ValueError, TypeError):
                continue

        return {
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "total_count": total,
        }
