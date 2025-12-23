import unittest
from unittest.mock import MagicMock, patch

from stock_monitor.data.fetcher import StockFetcher


class TestStockFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = StockFetcher()

    @patch("easyquotation.use")
    def test_fetch_a_stocks_limit(self, mock_use):
        # Mock easyquotation
        mock_quotation = MagicMock()
        mock_use.return_value = mock_quotation

        # Mock huge list
        mock_quotation.stock_list = [f"sh60{i:04d}" for i in range(12000)]

        # Since fetch_all_stocks calls _fetch_a_stocks internally
        # We can test _fetch_a_stocks directly or fetch_all_stocks
        # Note: fetch_all_stocks also calls fetch_hk_stocks etc.
        # Let's mock _fetch_hk_stocks and _fetch_indices to focus on A shares
        with patch.object(
            self.fetcher, "_fetch_hk_stocks", return_value=[]
        ), patch.object(self.fetcher, "_fetch_indices", return_value=[]):
            # Mock get_stock_data return empty dict to avoid processing
            mock_quotation.stocks.return_value = {}

            self.fetcher.fetch_all_stocks()

            # Check if it logged limitation (we can't easily check log here without capture)
            # But we can check how many batches were requested
            # 10000 limit / 800 batch = 13 batches
            self.assertEqual(mock_quotation.stocks.call_count, 13)

    @patch("requests.get")
    def test_fetch_hk_stocks_parsing(self, mock_get):
        # Mock Excel content
        # We need to construct a valid Excel file in bytes
        import io

        import pandas as pd

        df = pd.DataFrame(
            {
                "Code": [700, "00001", "invalid"],
                "Name": ["Tencent", "CK Hutchison", "Invalid"],
            }
        )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(
                writer, index=False, startrow=1
            )  # header=1 in read_excel means row 1 is header (0-indexed? usually row 0 is title, row 1 header)
            # pandas read_excel header=1 means skip first row (row 0) and use row 1 as header.
            # So we should put data starting from row 2?
            # Let's just create a simple excel

        # Creating a bytes buffer that pandas read_excel(header=1) can read
        # Using a simpler approach: create a DF, save to buffer.
        # Ensure row 0 is dummy, row 1 is header.

        data = [
            ["Title", "Title"],
            ["Code", "Name"],
            [700, "Tencent"],
            ["9988", "Alibaba"],
        ]
        df_full = pd.DataFrame(data)
        output = io.BytesIO()
        df_full.to_excel(
            output, index=False, header=False
        )  # Write without header, raw data

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = output.getvalue()
        mock_get.return_value = mock_response

        stocks = self.fetcher._fetch_hk_stocks()

        # Check results
        codes = [s["code"] for s in stocks]
        self.assertIn("hk00700", codes)
        self.assertIn("hk09988", codes)
