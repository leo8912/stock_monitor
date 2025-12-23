import unittest
import os
import sqlite3
import shutil
from unittest.mock import MagicMock, patch
from stock_monitor.data.stock.stock_db import StockDatabase

class TestStockDatabase(unittest.TestCase):
    def setUp(self):
        # Use a temporary database file for testing, unique per test to avoid locking issues
        self.test_db_path = f"test_stocks_{self._testMethodName}.db"
        # Mock get_config_dir to return current directory
        self.patcher_config = patch('stock_monitor.data.stock.stock_db.get_config_dir', return_value='.')
        self.mock_config_dir = self.patcher_config.start()
        
        # Mock DB_FILE constant to use our test db filename
        self.patcher_db_file = patch('stock_monitor.data.stock.stock_db.DB_FILE', self.test_db_path)
        self.patcher_db_file.start()
        
        # Reset the singleton instance
        StockDatabase._instance = None
        self.db = StockDatabase()
        
    def tearDown(self):
        self.patcher_config.stop()
        self.patcher_db_file.stop()
        StockDatabase._instance = None
        # Clean up the database file
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except PermissionError:
                pass

    def test_insert_stocks_batch(self):
        """Test inserting a batch of stocks"""
        stocks = [
            {'code': 'sh600000', 'name': 'Generic Bank', 'pinyin': 'pfyh', 'abbr': 'pfyh'},
            {'code': 'sz000001', 'name': 'Generic Tech', 'pinyin': 'payh', 'abbr': 'payh'},
            {'code': 'hk00700', 'name': 'Tencent', 'pinyin': 'txkg', 'abbr': 'txkg'}
        ]
        
        count = self.db.insert_stocks(stocks)
        self.assertEqual(count, 3)
        
        # Verify data
        stock1 = self.db.get_stock_by_code('sh600000')
        self.assertIsNotNone(stock1)
        self.assertEqual(stock1['name'], 'Generic Bank')
        self.assertEqual(stock1['code'], 'sh600000')

        stock2 = self.db.get_stock_by_code('hk00700')
        self.assertIsNotNone(stock2)
        self.assertEqual(stock2['name'], 'Tencent')
        
    def test_update_existing_stocks(self):
        """Test updating existing stocks"""
        # Initial insert
        stocks = [
            {'code': 'sh600000', 'name': 'Old Name', 'pinyin': 'on', 'abbr': 'on'}
        ]
        self.db.insert_stocks(stocks)
        
        # Update
        updated_stocks = [
            {'code': 'sh600000', 'name': 'New Name', 'pinyin': 'nn', 'abbr': 'nn'}
        ]
        count = self.db.insert_stocks(updated_stocks)
        self.assertEqual(count, 1)
        
        # Verify update
        stock = self.db.get_stock_by_code('sh600000')
        self.assertEqual(stock['name'], 'New Name')
        self.assertEqual(stock['abbr'], 'nn')

    def test_insert_mixed_new_and_existing(self):
        """Test inserting a mix of new and existing stocks"""
        # Initial insert
        self.db.insert_stocks([
            {'code': 'sh600000', 'name': 'Stock A', 'pinyin': 'a', 'abbr': 'a'}
        ])
        
        # Batch with 1 update and 1 new
        batch = [
            {'code': 'sh600000', 'name': 'Stock A', 'pinyin': 'a', 'abbr': 'a'}, # Unchanged
            {'code': 'sh600001', 'name': 'Stock B', 'pinyin': 'b', 'abbr': 'b'}  # New
        ]
        
        # Note: New optimized implementation returns total processed count (len(batch))
        # because tracking granular "unchanged" status is expensive in batch operations.
        count = self.db.insert_stocks(batch)
        
        self.assertEqual(count, 2) 
        
        self.assertEqual(self.db.get_all_stocks_count(), 2)

if __name__ == '__main__':
    unittest.main()
