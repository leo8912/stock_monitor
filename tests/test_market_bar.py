import sys

from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from stock_monitor.ui.widgets import MarketStatusBar


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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    sys.exit(app.exec_())
