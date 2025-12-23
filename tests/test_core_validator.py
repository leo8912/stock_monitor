import unittest

from stock_monitor.core.stock_data_validator import StockDataValidator


class TestStockDataValidator(unittest.TestCase):
    def setUp(self):
        self.validator = StockDataValidator()

    def test_is_valid_valid_data(self):
        """Test validation with valid data"""
        data = {"name": "Test", "now": 10.5, "close": 10.0}
        self.assertTrue(self.validator.is_valid(data))

        # String numbers should be valid (if castable)
        data_str = {"name": "Test", "now": "10.5", "close": "10.0"}
        self.assertTrue(self.validator.is_valid(data_str))

    def test_is_valid_invalid_data(self):
        """Test validation with invalid data"""
        # Missing keys
        self.assertFalse(self.validator.is_valid({"now": 10.0}))

        # None values
        self.assertFalse(self.validator.is_valid({"now": None, "close": 10.0}))

        # Non-numeric
        self.assertFalse(self.validator.is_valid({"now": "abc", "close": 10.0}))

    def test_handle_special_cases(self):
        """Test special case handling (e.g. Ping An Bank name fix)"""
        # 000001 case
        data = {"name": "Unknown"}

        # sh000001 -> Shanghai Index
        fixed_sh = self.validator.handle_special_cases(
            data, "000001", "sh000001", should_copy=True
        )
        self.assertEqual(fixed_sh["name"], "上证指数")
        # Ensure copy was made
        self.assertNotEqual(id(data), id(fixed_sh))

        # sz000001 -> Ping An Bank
        fixed_sz = self.validator.handle_special_cases(
            data, "000001", "sz000001", should_copy=True
        )
        self.assertEqual(fixed_sz["name"], "平安银行")

    def test_validate_required_fields(self):
        """Test full field validation"""
        complete_data = {
            "name": "Test",
            "now": 10.0,
            "close": 9.0,
            "open": 9.0,
            "high": 11.0,
            "low": 9.0,
            "volume": 1000,
        }
        self.assertTrue(self.validator.validate_required_fields(complete_data))

        incomplete_data = {"name": "Test"}
        self.assertFalse(self.validator.validate_required_fields(incomplete_data))


if __name__ == "__main__":
    unittest.main()
