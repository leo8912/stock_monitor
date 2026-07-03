"""
回测结果可视化弹窗
"""

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen


class BacktestResultDialog(QtWidgets.QDialog):
    """回测结果可视化弹窗"""

    def __init__(self, symbol: str, timeframe: str, result: dict, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.timeframe = timeframe
        self.result = result
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"回测结果 - {self.symbol} ({self.timeframe})")
        self.setMinimumSize(400, 300)
        self.resize(500, 350)

        # 暗色主题
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                font-family: "Microsoft YaHei";
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 16px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title = QtWidgets.QLabel(f"📊 {self.symbol} 回测结果")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffcc00;")
        layout.addWidget(title)

        # 时间周期
        tf_label = QtWidgets.QLabel(f"时间周期: {self.timeframe}")
        tf_label.setStyleSheet("font-size: 14px; color: #888888;")
        layout.addWidget(tf_label)

        # 结果统计
        stats_layout = QtWidgets.QGridLayout()
        stats_layout.setSpacing(10)

        # 总信号数
        total_signals = self.result.get("total_signals", 0)
        stats_layout.addWidget(
            self._create_stat_label("总信号数", str(total_signals)), 0, 0
        )

        # 胜率
        win_rate = self.result.get("win_rate", 0) * 100
        win_rate_color = "#2ca02c" if win_rate >= 60 else "#ff4a4a"
        stats_layout.addWidget(
            self._create_stat_label("胜率", f"{win_rate:.1f}%", win_rate_color), 0, 1
        )

        # 平均收益
        avg_profit = self.result.get("avg_profit", 0) * 100
        profit_color = "#2ca02c" if avg_profit >= 0 else "#ff4a4a"
        stats_layout.addWidget(
            self._create_stat_label("平均收益", f"{avg_profit:+.2f}%", profit_color),
            0,
            2,
        )

        layout.addLayout(stats_layout)

        # 简单条形图
        chart_widget = BacktestChartWidget(self.result)
        chart_widget.setMinimumHeight(120)
        layout.addWidget(chart_widget)

        # 关闭按钮
        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        close_button.setFixedWidth(100)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)

    def _create_stat_label(self, title: str, value: str, color: str = "#ffffff"):
        """创建统计标签"""
        container = QtWidgets.QVBoxLayout()
        container.setSpacing(2)

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("font-size: 12px; color: #888888; border: none;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container.addWidget(title_label)

        value_label = QtWidgets.QLabel(value)
        value_label.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {color}; border: none;"
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container.addWidget(value_label)

        widget = QtWidgets.QWidget()
        widget.setLayout(container)
        return widget


class BacktestChartWidget(QtWidgets.QWidget):
    """回测结果简单条形图"""

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self.result = result
        self.setMinimumHeight(120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 获取绘制区域
        rect = self.rect()
        width = rect.width()
        height = rect.height()

        # 绘制背景
        painter.fillRect(rect, QColor("#1e1e1e"))

        # 计算条形图参数
        win_rate = self.result.get("win_rate", 0) * 100
        avg_profit = self.result.get("avg_profit", 0) * 100
        total_signals = self.result.get("total_signals", 0)

        bar_width = 60
        bar_spacing = 40
        max_height = height - 40
        center_x = width // 2

        # 绘制胜率条
        bar_height = int((win_rate / 100) * max_height)
        bar_x = center_x - bar_width - bar_spacing // 2
        bar_y = height - 20 - bar_height

        # 胜率条颜色
        win_color = QColor("#2ca02c") if win_rate >= 60 else QColor("#ff4a4a")
        painter.setBrush(QBrush(win_color))
        painter.setPen(QPen(win_color))
        painter.drawRect(bar_x, bar_y, bar_width, bar_height)

        # 绘制胜率标签
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(
            bar_x,
            bar_y - 5,
            bar_width,
            20,
            Qt.AlignmentFlag.AlignCenter,
            f"{win_rate:.1f}%",
        )
        painter.drawText(
            bar_x, height - 15, bar_width, 20, Qt.AlignmentFlag.AlignCenter, "胜率"
        )

        # 绘制平均收益条
        profit_height = int((abs(avg_profit) / 10) * max_height)  # 假设最大10%
        profit_height = min(profit_height, max_height)
        bar_x2 = center_x + bar_spacing // 2
        bar_y2 = height - 20 - profit_height

        # 收益条颜色
        profit_color = QColor("#2ca02c") if avg_profit >= 0 else QColor("#ff4a4a")
        painter.setBrush(QBrush(profit_color))
        painter.setPen(QPen(profit_color))
        painter.drawRect(bar_x2, bar_y2, bar_width, profit_height)

        # 绘制收益标签
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(
            bar_x2,
            bar_y2 - 5,
            bar_width,
            20,
            Qt.AlignmentFlag.AlignCenter,
            f"{avg_profit:+.2f}%",
        )
        painter.drawText(
            bar_x2, height - 15, bar_width, 20, Qt.AlignmentFlag.AlignCenter, "平均收益"
        )

        # 绘制信号数
        painter.setPen(QPen(QColor("#888888")))
        painter.drawText(
            0, 5, width, 20, Qt.AlignmentFlag.AlignCenter, f"共 {total_signals} 个信号"
        )

        painter.end()
