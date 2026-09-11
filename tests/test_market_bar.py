import sys

from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from stock_monitor.ui.widgets import MarketStatusBar
from stock_monitor.ui.widgets.taskbar_quote_bar import TaskbarQuoteBar


class DemoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Market Status Bar Test")
        layout = QVBoxLayout()

        self.status_bar = MarketStatusBar()
        layout.addWidget(self.status_bar)

        self.button = QPushButton("Update Market Status")
        self.button.clicked.connect(self.status_bar.update_market_status)  # type: ignore
        layout.addWidget(self.button)

        self.setLayout(layout)
        self.resize(400, 100)


def test_taskbar_quote_bar_market_stats_update():
    QApplication.instance() or QApplication(sys.argv)
    bar = TaskbarQuoteBar()
    bar.update_market_stats(20, 15, 5, 40)
    assert bar._market_up_count == 20
    assert bar._market_down_count == 15
    assert bar._market_flat_count == 5
    assert bar._market_total_count == 40


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec_())
