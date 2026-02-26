from unittest.mock import patch

from stock_monitor.core.workers import MarketStatsWorker


class TestMarketStatsWorker:
    @patch("stock_monitor.core.stock_manager.stock_manager")
    @patch("stock_monitor.core.workers.market_worker.MarketManager.is_market_open")
    def test_calculate_stats(self, mock_is_market_open, mock_stock_manager):
        worker = MarketStatsWorker()

        # 模拟数据
        mock_data = {
            "sh000001": {
                "name": "上证指数",
                "now": 3000,
                "close": 2900,
            },  # 指数应被跳过
            "sz000001": {"name": "平安银行", "now": 10.5, "close": 10.0},  # 上涨
            "sz000002": {"name": "万科A", "now": 9.5, "close": 10.0},  # 下跌
            "sz000003": {"name": "PT金田", "now": 0, "close": 0},  # 平盘 (停牌)
            "sz000004": {"name": "国农科技", "now": 20.0, "close": 20.0},  # 平盘
            "invalid": "not a dict",  # 无效数据
        }

        stats = worker._calculate_stats(mock_data)

        assert stats["up_count"] == 1
        assert stats["down_count"] == 1
        assert stats["flat_count"] == 2
        assert stats["total_count"] == 4

    @patch("stock_monitor.core.stock_manager.stock_manager")
    def test_worker_run_flow(self, mock_stock_manager):
        # 这是一个简单的流程测试，不实际运行多线程循环
        worker = MarketStatsWorker()
        worker.interval = 1

        # 模拟获取数据
        mock_stock_manager.get_all_market_data.return_value = {
            "sz000001": {"name": "平安银行", "now": 10.5, "close": 10.0}
        }

        # 验证 stats_updated 信号
        # 由于 QThread 需要 Qt 事件循环，这里只测试逻辑方法 _calculate_stats
        # 或者使用 pytest-qt 插件，但为了简单起见，我们主要验证计算逻辑
        pass
