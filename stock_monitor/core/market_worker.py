from typing import Any

from PyQt6 import QtCore

from stock_monitor.config.manager import is_market_open
from stock_monitor.utils.logger import app_logger


class MarketStatsWorker(QtCore.QThread):
    """全市场统计工作线程"""

    # 信号：上涨数, 下跌数, 平盘数, 总数
    stats_updated = QtCore.pyqtSignal(int, int, int, int)

    def __init__(self):
        super().__init__()
        self._is_running = False
        self.interval = 60  # 默认60秒刷新一次
        self._last_data_time = None  # 记录上次数据时间戳
        self._market_closed_fetched = False  # 闭市数据已获取标志

    def start_worker(self):
        """启动工作线程"""
        if not self.isRunning():
            self._is_running = True
            self.start()
            app_logger.info("市场统计后台线程已启动")

    def stop_worker(self):
        """停止工作线程"""
        self._is_running = False
        self.wait(2000)
        app_logger.info("市场统计后台线程已停止")

    def run(self):
        """线程执行入口"""
        # 初始延迟
        self.msleep(2000)

        while self._is_running:
            try:
                # 检查市场是否开市，闭市期间延长刷新间隔
                market_open = is_market_open()
                app_logger.info(
                    f"[市场统计] 市场状态检查: {'开市' if market_open else '闭市'}"
                )

                # 临时注释：即使闭市也获取数据，用于调试
                # if not market_open:
                #      # 闭市期间每5分钟检查一次，或者直接sleep
                #      # 为了响应停止信号，使用循环sleep
                #      for _ in range(60):
                #          if not self._is_running: return
                #          self.sleep(5)
                #      continue

                app_logger.info("[市场统计] 开始获取全市场数据...")
                from stock_monitor.core.stock_manager import stock_manager

                market_data = stock_manager.get_all_market_data()

                if market_data:
                    app_logger.info(
                        f"[市场统计] 成功获取数据，共 {len(market_data)} 只股票"
                    )
                    stats = self._calculate_stats(market_data)
                    app_logger.info(
                        f"[市场统计] 统计结果: 上涨={stats['up_count']}, 下跌={stats['down_count']}, 平盘={stats['flat_count']}, 总计={stats['total_count']}"
                    )
                    self.stats_updated.emit(
                        stats["up_count"],
                        stats["down_count"],
                        stats["flat_count"],
                        stats["total_count"],
                    )
                    app_logger.info("[市场统计] 已发送更新信号")
                else:
                    app_logger.warning("[市场统计] 获取全市场数据失败，返回None")

                # 休眠
                for _ in range(self.interval):
                    if not self._is_running:
                        break
                    self.sleep(1)

            except Exception as e:
                app_logger.error(f"市场统计线程异常: {e}")
                self.sleep(10)

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
            # 跳过指数
            if "指数" in name or "Ａ股" in name:
                continue

            try:
                close = float(info.get("close", 0))
                now = float(info.get("now", 0))

                if close == 0:
                    flat += 1
                elif now > close:
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

    def _get_data_timestamp(self, data: dict[str, Any]) -> str:
        """
        获取市场数据的时间戳

        Args:
            data: 市场数据字典

        Returns:
            str: 时间戳字符串，格式为 "YYYY-MM-DD HH:MM:SS"
        """
        # 从任意一只股票获取时间
        for _code, info in data.items():
            if isinstance(info, dict):
                date = info.get("date", "")
                time = info.get("time", "")
                if date and time:
                    return f"{date} {time}"
        return ""
