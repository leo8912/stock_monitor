from stock_monitor.data.stock.stock_db import stock_db
from stock_monitor.ui.main_window import MainWindow


def test_main_window_init(qtbot, monkeypatch):
    """
    GUI冒烟测试：验证主窗口能否正常初始化
    """
    # 模拟数据防止自动更新触发网络请求
    monkeypatch.setattr(stock_db, "is_empty", lambda: False)
    monkeypatch.setattr(stock_db, "get_all_stocks", lambda: [])

    # 模拟 RefreshWorker 防止线程未退出导致崩溃
    from unittest.mock import MagicMock

    mock_worker = MagicMock()
    # 确保 data_updated 和 refresh_error 信号存在
    mock_worker.data_updated.connect = MagicMock()
    mock_worker.refresh_error.connect = MagicMock()
    mock_worker.start_refresh = MagicMock()

    # 替换 RefreshWorker 类，使其返回我们的 mock_worker
    # 注意：RefreshWorker 在 main_window.py 中被导入，所以要 patch 那里的引用
    import stock_monitor.ui.main_window

    monkeypatch.setattr(
        stock_monitor.ui.main_window, "RefreshWorker", lambda: mock_worker
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
