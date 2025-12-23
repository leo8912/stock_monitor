import unittest
from unittest.mock import MagicMock, patch
from stock_monitor.core.stock_data_fetcher import StockDataFetcher

class TestStockDataFetcher(unittest.TestCase):
    def setUp(self):
        patcher = patch('easyquotation.use')
        self.mock_init_use = patcher.start()
        self.addCleanup(patcher.stop)
        self.fetcher = StockDataFetcher()
        # Ensure we start with a clean mock for each test if needed, 
        # though individual tests set it again.
        # But importantly, __init__ didn't fail.

    def test_fetch_single_a_stock(self):
        """Test fetching a single A-share stock"""
        mock_quotation = MagicMock()
        
        # Mock successful response
        mock_quotation.stocks.return_value = {
            'sh600000': {'name': '浦发银行', 'now': 10.0}
        }
        
        # Inject mock engine directly
        self.fetcher.sina_quotation = mock_quotation
        
        result = self.fetcher.fetch_single('sh600000')
        
        self.assertIsNotNone(result)
        self.assertIn('sh600000', result)
        self.assertEqual(result['sh600000']['name'], '浦发银行')
        self.assertEqual(result['sh600000']['now'], 10.0)
        
        # Test retry logic on failure
        mock_quotation.stocks.side_effect = [Exception("Network error"), {'sh600000': {'name': 'Retry', 'now': 10.1}}]
        result_retry = self.fetcher.fetch_single('sh600000')
        self.assertIsNotNone(result_retry)
        self.assertEqual(result_retry['sh600000']['name'], 'Retry')

    def test_fetch_multiple_stocks(self):
        """Test fetching multiple stocks (A-share and HK)"""
        mock_quotation = MagicMock()
        self.fetcher.sina_quotation = mock_quotation
        
        # Mock A-share response
        mock_quotation.stocks.return_value = {
            'sh600000': {'name': '浦发银行', 'now': 10.0}
        }
        
        codes = ['sh600000']
        result = self.fetcher.fetch_multiple(codes)
        self.assertIn('sh600000', result)
        self.assertEqual(result['sh600000']['name'], '浦发银行')

    def test_fetch_hk_stock_logic(self):
        """Test HK stock fetching logic"""
        # Configure the patcher from setUp to return our mock for HK
        mock_hk_engine = MagicMock()
        self.mock_init_use.return_value = mock_hk_engine
        
        mock_hk_engine.stocks.return_value = {'00700': {'name': 'Tencent', 'now': 300.0}}
        
        # "fetch_single" with 'hk...' calls get_quotation_engine -> easyquotation.use('hkquote')
        # which calls self.mock_init_use('hkquote')
        
        result = self.fetcher.fetch_single('hk00700')
        
        # Verify result
        self.assertIsNotNone(result)
        # Verify 'hkquote' was initialized (called on the mock)
        self.mock_init_use.assert_any_call('hkquote')

if __name__ == '__main__':
    unittest.main()
