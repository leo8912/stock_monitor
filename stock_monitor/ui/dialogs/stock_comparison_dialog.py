"""
多只股票对比弹窗
"""

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from ...utils.logger import app_logger


class _DataLoadWorker(QThread):
    """后台数据拉取线程，避免阻塞 UI。"""

    finished = pyqtSignal(list)  # 成功时发送 comparison_data 列表
    error = pyqtSignal(str)  # 失败时发送错误信息

    def __init__(self, engine, symbols, stock_names, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.symbols = symbols
        self.stock_names = stock_names

    def run(self):
        comparison_data = []
        try:
            for symbol in self.symbols:
                try:
                    df = self.engine.fetch_bars(symbol, category=9, offset=250)
                    if df is None or df.empty or len(df) < 60:
                        continue

                    indicators = self.engine.calculate_comprehensive_indicators(df)
                    if not indicators:
                        continue

                    current_price = df.iloc[-1]["close"]
                    prev_price = df.iloc[-2]["close"] if len(df) > 1 else current_price
                    pct_change = (
                        (current_price - prev_price) / prev_price * 100
                        if prev_price
                        else 0.0
                    )

                    rsi = indicators.get("rsi", 0)
                    if rsi == 0 and "RSI_14" in df.columns:
                        rsi = df["RSI_14"].iloc[-1]

                    trend = indicators.get("trend", "震荡")
                    trend_color = (
                        "#ff4a4a"
                        if "多头" in trend
                        else "#2ca02c"
                        if "空头" in trend
                        else "#ffcc00"
                    )

                    signals = []
                    if self.engine.check_macd_bullish_divergence(df):
                        signals.append("MACD底背离")
                    if self.engine.check_bbands_squeeze(df):
                        signals.append("BB收口")
                    if self.engine.check_accumulation(df):
                        signals.append("OBV吸筹")

                    strength = indicators.get("strength", "")

                    comparison_data.append({
                        "symbol": symbol,
                        "name": self.stock_names.get(symbol, symbol),
                        "price": current_price,
                        "pct_change": pct_change,
                        "rsi": rsi,
                        "trend": trend,
                        "trend_color": trend_color,
                        "signals": signals,
                        "strength": strength,
                    })

                except Exception as e:
                    app_logger.warning(f"[股票对比] 获取 {symbol} 数据失败: {e}")
                    continue

            self.finished.emit(comparison_data)
        except Exception as e:
            self.error.emit(str(e))


class StockComparisonDialog(QtWidgets.QDialog):
    """多只股票对比弹窗"""

    def __init__(
        self, engine, symbols: list[str], stock_names: dict, parent=None
    ) -> None:
        """初始化对比弹窗。

        Args:
            engine: 量化/行情引擎，用于拉取指标与信号。
            symbols: 待对比的股票代码列表。
            stock_names: 代码到名称的映射。
            parent: 父窗口。
        """
        super().__init__(parent)
        self.engine = engine
        self.symbols = symbols
        self.stock_names = stock_names
        self.comparison_data = []
        self._data_worker = None
        self.setup_ui()
        self.load_data()

    def setup_ui(self) -> None:
        """构建对比弹窗的界面（暗色主题表格 + 刷新/关闭按钮）。"""
        self.setWindowTitle("📊 股票技术指标对比")
        self.setMinimumSize(800, 500)
        self.resize(1000, 600)

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
            QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 4px;
                gridline-color: #333333;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #333333;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                border: 1px solid #333333;
                padding: 8px;
                color: #ffffff;
                font-weight: bold;
            }
        """)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title = QtWidgets.QLabel("📊 股票技术指标对比")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffcc00;")
        layout.addWidget(title)

        # 对比表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["股票", "当前价", "涨跌幅", "RSI", "趋势", "信号", "强度"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #222222;
            }
        """)
        layout.addWidget(self.table)

        # 刷新按钮
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        refresh_button = QtWidgets.QPushButton("🔄 刷新数据")
        refresh_button.clicked.connect(self.load_data)
        button_layout.addWidget(refresh_button)

        close_button = QtWidgets.QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_data(self) -> None:
        """在后台线程中加载股票数据，完成后回到主线程填充表格。"""
        self.table.setRowCount(0)
        self.comparison_data = []

        # 禁用刷新按钮，防止重复触发
        self._set_refresh_enabled(False)

        self._data_worker = _DataLoadWorker(
            self.engine, self.symbols, self.stock_names, self
        )
        self._data_worker.finished.connect(self._on_data_loaded)
        self._data_worker.error.connect(self._on_data_error)
        self._data_worker.start()

    def _on_data_loaded(self, data: list) -> None:
        """后台线程完成后的回调：在主线程填充表格。"""
        self.comparison_data = data
        self._populate_table()
        self._set_refresh_enabled(True)

    def _on_data_error(self, error_msg: str) -> None:
        """后台线程出错时的回调。"""
        self._set_refresh_enabled(True)
        app_logger.error(f"[股票对比] 加载数据失败: {error_msg}")
        QtWidgets.QMessageBox.critical(self, "错误", f"加载数据失败: {error_msg}")

    def _set_refresh_enabled(self, enabled: bool) -> None:
        """启用/禁用刷新按钮。"""
        for btn in self.findChildren(QtWidgets.QPushButton):
            if "刷新" in (btn.text() or ""):
                btn.setEnabled(enabled)

    def _populate_table(self) -> None:
        """根据 self.comparison_data 填充表格（仅在主线程调用）。"""
        try:
            self.table.setRowCount(len(self.comparison_data))
            for row, data in enumerate(self.comparison_data):
                # 股票名称
                name_item = QtWidgets.QTableWidgetItem(
                    f"{data['name']}\n{data['symbol']}"
                )
                name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, name_item)

                # 当前价格
                price_item = QtWidgets.QTableWidgetItem(f"{data['price']:.2f}")
                price_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, price_item)

                # 涨跌幅
                pct_item = QtWidgets.QTableWidgetItem(f"{data['pct_change']:+.2f}%")
                pct_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if data["pct_change"] > 0:
                    pct_item.setForeground(QColor("#ff4a4a"))
                elif data["pct_change"] < 0:
                    pct_item.setForeground(QColor("#2ca02c"))
                self.table.setItem(row, 2, pct_item)

                # RSI
                rsi_item = QtWidgets.QTableWidgetItem(f"{data['rsi']:.1f}")
                rsi_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if data["rsi"] > 70:
                    rsi_item.setForeground(QColor("#ff4a4a"))
                elif data["rsi"] < 30:
                    rsi_item.setForeground(QColor("#2ca02c"))
                self.table.setItem(row, 3, rsi_item)

                # 趋势
                trend_item = QtWidgets.QTableWidgetItem(data["trend"])
                trend_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                trend_item.setForeground(QColor(data["trend_color"]))
                self.table.setItem(row, 4, trend_item)

                # 信号
                signals_text = ", ".join(data["signals"]) if data["signals"] else "-"
                signals_item = QtWidgets.QTableWidgetItem(signals_text)
                signals_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 5, signals_item)

                # 强度
                strength_item = QtWidgets.QTableWidgetItem(data["strength"])
                strength_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 6, strength_item)

            # 调整列宽
            self.table.resizeColumnsToContents()

        except Exception as e:
            app_logger.error(f"[股票对比] 填充表格失败: {e}")
