import unittest

from stock_monitor.core.stock_manager import StockManager


class TestStockManager(unittest.TestCase):
    def setUp(self):
        self.manager = StockManager()

    def test_change_detection(self):
        # Initial state: no cache
        stocks = [("StockA", "10.0", "1.0%", "#f00", "100", "B")]

        # Should detect change initially (empty cache)
        self.assertTrue(self.manager.has_stock_data_changed(stocks))

        # Update cache
        self.manager.update_last_stock_data(stocks)

        # Should NOT detect change with same data
        self.assertFalse(self.manager.has_stock_data_changed(stocks))

        # Change price
        changed_stocks = [("StockA", "10.1", "2.0%", "#f00", "100", "B")]
        self.assertTrue(self.manager.has_stock_data_changed(changed_stocks))

        # Update cache again
        self.manager.update_last_stock_data(changed_stocks)
        self.assertFalse(self.manager.has_stock_data_changed(changed_stocks))

        # Test remove stock
        self.assertTrue(self.manager.has_stock_data_changed([]))

        # Test add new stock
        new_stocks = [
            ("StockA", "10.1", "2.0%", "#f00", "100", "B"),
            ("StockB", "5.0", "0.0%", "#fff", "50", "S"),
        ]
        self.assertTrue(self.manager.has_stock_data_changed(new_stocks))
