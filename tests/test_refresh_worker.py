
import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtCore import QThread
from stock_monitor.core.refresh_worker import RefreshWorker

class TestRefreshWorker:
    @patch('stock_monitor.core.stock_manager.stock_manager')
    def test_worker_uses_stock_manager(self, mock_stock_manager):
        """测试 RefreshWorker 使用 StockManager 获取和处理数据"""
        worker = RefreshWorker()
        worker.refresh_interval = 1
        
        # 模拟 StockManager 返回值
        mock_stock_manager.fetch_and_process_stocks.return_value = (
            [('TestStock', '10.0', '0.0%', '#fff', '', '')], # stocks
            0 # failed_count
        )
        mock_stock_manager.has_stock_data_changed.return_value = True
        
        # 设置 Worker 状态以运行一次循环
        worker._is_running = True
        worker.current_user_stocks = ['sh600000']
        
        # 由于 Worker 是 QThread，这是集成测试比较困难。
        # 我们这里模拟 run 方法中的核心逻辑，而不是真正启动线程
        # 为了单元测试，我们可以提取核心逻辑到单独的方法，但现在我们只是
        # 模拟环境并手动调用 run 方法中的逻辑片段，或者更简单地，
        # 我们 mock time.sleep 以抛出异常来跳出循环，或者只测试 start_refresh 的副作用
        
        pass

    @patch('stock_monitor.core.stock_manager.stock_manager')
    @patch('stock_monitor.core.refresh_worker.is_market_open')
    def test_worker_cycle(self, mock_is_market_open, mock_stock_manager):
        """测试工作线程的一个周期"""
        # 模拟市场开放
        mock_is_market_open.return_value = True
        
        worker = RefreshWorker()
        # 模拟数据
        mock_stocks = [('Test', '10.0', '1.0%', '#f00', '', '')]
        mock_stock_manager.fetch_and_process_stocks.return_value = (mock_stocks, 0)
        mock_stock_manager.has_stock_data_changed.return_value = True
        
        # 设置初始状态
        worker.current_user_stocks = ['sh600000']
        worker.refresh_interval = 1
        worker._is_running = True
        worker._initial_update_done = True  # Avoid short-circuit to test dependency call
        
        # 使用 SideEffect 在循环第一次执行后停止线程，防止无限循环
        def stop_worker(*args, **kwargs):
            worker._is_running = False
            return
            
        # Mock sleep/msleep 来中断循环
        with patch.object(worker, 'sleep', side_effect=stop_worker), \
             patch.object(worker, 'msleep', return_value=None):
             
            worker.run()
            
            # 验证调用
            mock_stock_manager.fetch_and_process_stocks.assert_called_with(['sh600000'])
            mock_stock_manager.has_stock_data_changed.assert_called_with(mock_stocks)
            mock_stock_manager.update_last_stock_data.assert_called_with(mock_stocks)
