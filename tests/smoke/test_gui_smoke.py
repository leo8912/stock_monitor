from stock_monitor.core.container import container
from stock_monitor.data.stock.stock_db import StockDatabase
from stock_monitor.ui.main_window import MainWindow


def test_main_window_init(qtbot, monkeypatch):
    """
    GUI冒烟测试：验证主窗口能否正常初始化
    """
    # 模拟数据防止自动更新触发网络请求
    stock_db = container.get(StockDatabase)
    monkeypatch.setattr(stock_db, "is_empty", lambda: False)
    monkeypatch.setattr(stock_db, "get_all_stocks", lambda: [])

    # 模拟 RefreshWorker 防止线程未退出导致崩溃
    from unittest.mock import MagicMock

    mock_worker = MagicMock()
    # 确保 data_updated 和 refresh_error 信号存在
    mock_worker.data_updated.connect = MagicMock()
    mock_worker.refresh_error.connect = MagicMock()
    mock_worker.start_refresh = MagicMock()

    # 替换 ViewModel 中的 Workers
    import stock_monitor.ui.view_models.main_window_view_model
    
    monkeypatch.setattr(
        stock_monitor.ui.view_models.main_window_view_model, "RefreshWorker", lambda: mock_worker
    )
    
    # Mock MarketStatsWorker as well
    mock_market_worker = MagicMock()
    mock_market_worker.stats_updated.connect = MagicMock()
    mock_market_worker.start_worker = MagicMock()
    
    monkeypatch.setattr(
        stock_monitor.ui.view_models.main_window_view_model, "MarketStatsWorker", lambda: mock_market_worker
    )

    # 初始化主窗口
    window = MainWindow()
    qtbot.addWidget(window)

    # 验证窗口是否成功创建
    assert window is not None
    assert window.windowTitle() == "A股行情监控"

    # 验证基本控件是否存在
    assert hasattr(window, "table")
    assert hasattr(window, "market_status_bar")

    # 尝试显示窗口（不阻塞）
    window.show()
    assert window.isVisible()
