import unittest

from PyQt6 import QtCore

from stock_monitor.ui.models.stock_model import StockTableModel


class TestStockTableModel(unittest.TestCase):
    def setUp(self):
        self.model = StockTableModel()
        # Mock data: name, price, change, color, seal_vol, seal_type
        self.test_data = [
            ("平安银行", "10.50", "1.23", "#ff0000", "", ""),
            ("贵州茅台", "1800.00", "-2.5%", "#00ff00", "", ""),
            ("hk00700:腾讯控股", "350.00", "0.50", "#ff0000", "", ""),
            ("ST某某", "5.00", "5.00%", "#ff0000", "1000", "up"),
        ]

    def test_row_column_count(self):
        self.model.update_data(self.test_data)
        self.assertEqual(self.model.rowCount(), 4)
        self.assertEqual(
            self.model.columnCount(), 4
        )  # Should include seal column due to 4th item

        self.model.update_data(self.test_data[:3])
        self.assertEqual(self.model.rowCount(), 3)
        self.assertEqual(self.model.columnCount(), 3)  # No seal column

    def test_data_display(self):
        self.model.update_data(self.test_data)

        # Test Name Formatting
        idx_pingan = self.model.index(0, 0)
        self.assertEqual(
            self.model.data(idx_pingan, QtCore.Qt.ItemDataRole.DisplayRole), " 平安银行"
        )

        idx_tencent = self.model.index(2, 0)
        self.assertEqual(
            self.model.data(idx_tencent, QtCore.Qt.ItemDataRole.DisplayRole), " 腾讯控股"
        )

        # Test Price
        idx_price = self.model.index(0, 1)
        self.assertEqual(
            self.model.data(idx_price, QtCore.Qt.ItemDataRole.DisplayRole), "10.50"
        )

        # Test Change Formatting
        idx_change_raw = self.model.index(0, 2)
        self.assertEqual(
            self.model.data(idx_change_raw, QtCore.Qt.ItemDataRole.DisplayRole), "1.23%"
        )

        idx_change_pct = self.model.index(1, 2)
        self.assertEqual(
            self.model.data(idx_change_pct, QtCore.Qt.ItemDataRole.DisplayRole),
            "-2.5% ",
        )

    def test_colors(self):
        self.model.update_data(self.test_data)

        # Normal Up
        idx = self.model.index(0, 1)
        bg = self.model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole)
        fg = self.model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole)
        self.assertIsNone(bg)  # No background for normal
        self.assertEqual(fg.name(), "#ff0000")

        # Limit Up (Seal)
        idx_limit_up = self.model.index(3, 1)
        bg = self.model.data(idx_limit_up, QtCore.Qt.ItemDataRole.BackgroundRole)
        fg = self.model.data(idx_limit_up, QtCore.Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(bg.name(), "#ffecec")
        self.assertEqual(fg.name(), "#ff0000")

    def test_alignment(self):
        self.model.update_data(self.test_data)

        # Name should be left aligned
        align_name = self.model.data(
            self.model.index(0, 0), QtCore.Qt.ItemDataRole.TextAlignmentRole
        )
        self.assertTrue(align_name & QtCore.Qt.AlignmentFlag.AlignLeft)

        # Price should be right aligned
        align_price = self.model.data(
            self.model.index(0, 1), QtCore.Qt.ItemDataRole.TextAlignmentRole
        )
        self.assertTrue(align_price & QtCore.Qt.AlignmentFlag.AlignRight)


if __name__ == "__main__":
    unittest.main()
