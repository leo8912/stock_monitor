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

        with (
            patch.object(self.fetcher, "_fetch_hk_stocks", return_value=[]),
            patch.object(self.fetcher, "_fetch_indices", return_value=[]),
        ):
            mock_quotation.stocks.return_value = {}
            self.fetcher.fetch_all_stocks()
            self.assertEqual(mock_quotation.stocks.call_count, 13)

    def test_fetch_hk_stocks_parsing(self):
        """解析港股 Excel 数据"""
        import io

        import pandas as pd

        data = [
            ["Title", "Title"],
            ["Code", "Name"],
            [700, "Tencent"],
            ["9988", "Alibaba"],
        ]
        df_full = pd.DataFrame(data)
        output = io.BytesIO()
        df_full.to_excel(output, index=False, header=False)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = output.getvalue()

        mock_network = MagicMock()
        mock_network.get.return_value = mock_response

        with patch.object(self.fetcher, "_network", mock_network):
            stocks = self.fetcher._fetch_hk_stocks()

        codes = [s["code"] for s in stocks]
        self.assertIn("hk00700", codes)
        self.assertIn("hk09988", codes)

    def test_fetch_hk_stocks_http_error(self):
        """HTTP 非200返回时应返回空列表，不抛异常"""
        mock_network = MagicMock()
        mock_network.get.return_value = None

        with patch.object(self.fetcher, "_network", mock_network):
            stocks = self.fetcher._fetch_hk_stocks()
        self.assertEqual(stocks, [])

    def test_fetch_hk_stocks_timeout(self):
        """请求超时时应返回空列表，不抛异常"""
        mock_network = MagicMock()
        mock_network.get.return_value = None

        with patch.object(self.fetcher, "_network", mock_network):
            stocks = self.fetcher._fetch_hk_stocks()
        self.assertEqual(stocks, [])
