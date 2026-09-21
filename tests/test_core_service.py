import unittest
from unittest.mock import MagicMock

from stock_monitor.core.stock_service import StockDataService


class TestStockDataService(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_fetcher = MagicMock()
        self.mock_validator = MagicMock()
        self.mock_processor = MagicMock()

        self.service = StockDataService(
            fetcher=self.mock_fetcher,
            validator=self.mock_validator,
            processor=self.mock_processor,
        )

    def test_get_multiple_stocks_data(self):
        """Test batch stock data retrieval"""
        codes = ["sh600000"]
        raw_data = {"sh600000": {"name": "PF Bank", "now": 10.0}}
        self.mock_fetcher.fetch_multiple.return_value = raw_data

        result = self.service.get_multiple_stocks_data(codes)

        self.mock_fetcher.fetch_multiple.assert_called_with(codes)
        self.assertEqual(result, raw_data)

    def test_process_stock_data(self):
        """Test processing of stock data"""
        codes = ["sh600000"]
        raw_data = {"sh600000": {"name": "PF Bank", "now": 10.0}}

        # Mock validator
        self.mock_validator.get_stock_info.side_effect = lambda data, code: data.get(
            code
        )

        # Mock processor
        processed_item = ("PF Bank", "10.0", "1.0%", "#f00", "100", "B")
        self.mock_processor.process_raw_data.return_value = processed_item

        result = self.service.process_stock_data(raw_data, codes)

        self.mock_processor.process_raw_data.assert_called()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], processed_item)

    def test_get_stock_data_single(self):
        """Test getting single stock data"""
        code = "sh600000"
        raw_data = {"name": "PF Bank"}
        self.mock_fetcher.fetch_single.return_value = raw_data

        result = self.service.get_stock_data(code)

        self.mock_fetcher.fetch_single.assert_called_with(code)
        self.assertEqual(result, raw_data)

    def test_get_stocks_data_fetcher_exception(self):
        """Test that fetcher exceptions propagate through service methods"""
        self.mock_fetcher.fetch_multiple.side_effect = ConnectionError(
            "Network failure"
        )

        with self.assertRaises(ConnectionError):
            self.service.get_multiple_stocks_data(["sh600000"])

        self.mock_fetcher.fetch_single.side_effect = TimeoutError("Request timed out")
        with self.assertRaises(TimeoutError):
            self.service.get_stock_data("sh600000")

    def test_get_stocks_data_empty_fetcher(self):
        """Test that empty data from fetcher is returned as-is"""
        self.mock_fetcher.fetch_multiple.return_value = {}
        result = self.service.get_multiple_stocks_data(["sh600000"])
        self.assertEqual(result, {})
        self.mock_fetcher.fetch_multiple.assert_called_once()

    def test_get_stocks_data_partial_failure(self):
        """Test batch retrieval when fetcher returns mixed results (some None)"""
        raw_data = {
            "sh600000": {"name": "PF Bank", "now": 10.0},
            "sh601398": None,
        }
        self.mock_fetcher.fetch_multiple.return_value = raw_data

        result = self.service.get_multiple_stocks_data(["sh600000", "sh601398"])

        self.assertEqual(result, raw_data)
        # Data for failed stock is None; successful stock has data
        self.assertIsNotNone(result["sh600000"])
        self.assertIsNone(result["sh601398"])


if __name__ == "__main__":
    unittest.main()
