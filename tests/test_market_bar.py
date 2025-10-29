import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from stock_monitor.ui.market_status import MarketStatusBar

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Market Status Bar Test')
        layout = QVBoxLayout()
        
        self.status_bar = MarketStatusBar()
        layout.addWidget(self.status_bar)
        
        self.button = QPushButton('Update Market Status')
        self.button.clicked.connect(self.status_bar.update_market_status)
        layout.addWidget(self.button)
        
        self.setLayout(layout)
        self.resize(400, 100)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())