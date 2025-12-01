import unittest
import os
import json
import redis
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from quota import QuotaManager, DAILY_LIMIT

class TestQuotaManager(unittest.TestCase):
    @patch('redis.from_url')
    def setUp(self, mock_redis_from_url):
        self.mock_redis_client = MagicMock()
        mock_redis_from_url.return_value = self.mock_redis_client
        
        # Simulate Redis data in memory
        self._mock_redis_data = {} 
        self.mock_redis_client.hget.side_effect = lambda k, f: self._mock_redis_data.get(k, {}).get(f)
        self.mock_redis_client.hset.side_effect = lambda k, f, v: self._mock_redis_data.setdefault(k, {}) .__setitem__(f, v)
        self.mock_redis_client.flushdb.side_effect = lambda: self._mock_redis_data.clear()

        self.qm = QuotaManager()
        self.qm.r = self.mock_redis_client # Ensure qm uses our mock
        
        # Clear mock Redis before each test
        self.mock_redis_client.flushdb()


    def test_initial_check(self):
        self.assertTrue(self.qm.check_quota('user1'))
        self.mock_redis_client.hget.assert_called_with('download_quota:user1', 'data')

    def test_usage_tracking(self):
        self.qm.add_usage('user1', 1024) # 1KB
        self.assertTrue(self.qm.check_quota('user1'))
        
        expected_data = {'date': self.qm._get_today_str(), 'bytes_used': 1024}
        self.mock_redis_client.hset.assert_called_with('download_quota:user1', 'data', json.dumps(expected_data))

    def test_quota_exceeded(self):
        self.qm.add_usage('user1', DAILY_LIMIT)
        # Check should now be false since bytes_used == DAILY_LIMIT
        self.assertFalse(self.qm.check_quota('user1'))
        
        # Add one more byte just to be sure
        self.qm.add_usage('user1', 1)
        self.assertFalse(self.qm.check_quota('user1'))

    @patch('quota.QuotaManager._get_today_str')
    def test_daily_reset(self, mock_get_today_str):
        # Simulate yesterday's date
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        mock_get_today_str.return_value = yesterday_str

        # Add usage for 'user1' on yesterday
        self.qm.add_usage('user1', DAILY_LIMIT + 100)
        
        # Simulate today's date
        today_str = datetime.now().strftime('%Y-%m-%d')
        mock_get_today_str.return_value = today_str

        # Calling check_quota should trigger the reset because the date has changed
        self.assertTrue(self.qm.check_quota('user1'))
        
        # Verify reset in mock Redis
        key = 'download_quota:user1'
        retrieved_data_str = self.mock_redis_client.hget(key, 'data')
        self.assertIsNotNone(retrieved_data_str)
        retrieved_data = json.loads(retrieved_data_str)
        self.assertEqual(retrieved_data['bytes_used'], 0)
        self.assertEqual(retrieved_data['date'], today_str)
        
if __name__ == '__main__':
    unittest.main()
