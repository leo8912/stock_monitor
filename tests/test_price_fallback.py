import unittest
from stock_monitor.core.stock_data_processor import StockDataProcessor

class TestPriceFallback(unittest.TestCase):
    def setUp(self):
        self.processor = StockDataProcessor()
        
    def test_processor_fallback_none(self):
        """Test StockDataProcessor falls back to close when now is None"""
        code = "sh600000"
        # Mock data where now is None
        data = {
            "name": "Test Stock",
            "now": None,
            "close": "10.00",
            "price": None,
            "lastPrice": "10.00"
        }
        
        result = self.processor.process_raw_data(code, data)
        
        self.assertIsNotNone(result)
        # Expected tuple: (name, price, change_pct, color, ...)
        name, price, change, color, _, _ = result
        self.assertEqual(price, "10.00")
        self.assertEqual(change, "+0.00%")
        
    def test_processor_fallback_zero(self):
        """Test StockDataProcessor falls back to close when now is 0"""
        code = "sh600000"
        data = {
            "name": "Test Stock",
            "now": "0.00", # String "0.00"
            "close": "10.00",
            "price": "0.00",
            "lastPrice": "10.00"
        }
        
        result = self.processor.process_raw_data(code, data)
        
        self.assertIsNotNone(result)
        name, price, change, color, _, _ = result
        self.assertEqual(price, "10.00")
        self.assertEqual(change, "+0.00%")

    def test_processor_normal(self):
        """Test StockDataProcessor uses now when valid"""
        code = "sh600000"
        data = {
            "name": "Test Stock",
            "now": "11.00",
            "close": "10.00",
            "price": "11.00",
            "lastPrice": "10.00"
        }
        
        result = self.processor.process_raw_data(code, data)
        self.assertIsNotNone(result)
        name, price, change, color, _, _ = result
        self.assertEqual(price, "11.00")
        self.assertEqual(change, "+10.00%")
        
if __name__ == '__main__':
    unittest.main()
