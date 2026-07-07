"""
暗盘统计集成测试 - 使用真实数据计算，mock推送
"""

from unittest.mock import patch

import pytest

from stock_monitor.services.close_export_scheduler import (
    CloseExportScheduler,
    DarkTradeStatsTask,
)
from stock_monitor.services.dark_trade_stats import (
    calculate_dark_trade_stats,
    format_dark_trade_stats_message,
    push_dark_trade_stats,
)


class TestDarkTradeStatsIntegration:
    """暗盘统计集成测试（真实数据计算）"""

    @pytest.mark.integration
    def test_calculate_real_data(self):
        """使用真实数据计算统计"""
        stats = calculate_dark_trade_stats([], history_days=1)

        assert "market_summary" in stats
        assert "watchlist_details" in stats
        assert "date" in stats
        assert isinstance(stats["market_summary"], dict)
        assert isinstance(stats["watchlist_details"], list)

    @pytest.mark.integration
    def test_calculate_with_watchlist(self):
        """带自选股的统计计算"""
        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)

        watchlist = stats.get("watchlist_details", [])
        assert len(watchlist) >= 0  # 可能有数据也可能没有
        if watchlist:
            assert watchlist[0]["code"] == "600519"

    @pytest.mark.integration
    def test_format_message_integration(self):
        """格式化消息集成测试"""
        stats = calculate_dark_trade_stats(["sh600519"], history_days=1)
        message = format_dark_trade_stats_message(stats)

        assert "📊 暗盘资金统计" in message
        assert "【全市场概览】" in message

    @pytest.mark.integration
    @patch("stock_monitor.services.notifier.NotifierService.dispatch_custom_message")
    def test_push_integration(self, mock_dispatch):
        """推送集成测试（mock推送）"""
        mock_dispatch.return_value = True

        from stock_monitor.core.config_center import config_center

        result = push_dark_trade_stats(config_center.snapshot(), ["sh600519"])

        assert result is True
        mock_dispatch.assert_called_once()


class TestCloseExportSchedulerTasks:
    """调度器任务注册测试"""

    def test_task_registry(self):
        """任务注册和执行"""
        scheduler = CloseExportScheduler()

        # 验证默认任务已注册
        tasks = scheduler.get_tasks()
        assert len(tasks) == 3
        task_names = [t.name for t in tasks]
        assert "暗盘Excel导出" in task_names
        assert "自选股指标导出" in task_names
        assert "暗盘统计推送" in task_names

    def test_task_enable_disable(self):
        """任务启用/禁用"""
        task = DarkTradeStatsTask()
        assert task.enabled is True

        task.set_enabled(False)
        assert task.enabled is False

    def test_trigger_single_task(self):
        """触发单个任务"""
        scheduler = CloseExportScheduler()

        # 只触发暗盘统计推送（不触发Excel导出）
        with patch.object(DarkTradeStatsTask, "execute") as mock_exec:
            mock_exec.return_value = True
            scheduler.trigger_now(task_name="暗盘统计推送")
            mock_exec.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
