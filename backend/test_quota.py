import unittest
import os
import json
from quota import QuotaManager, DAILY_LIMIT

class TestQuotaManager(unittest.TestCase):
    def setUp(self):
        self.test_file = 'test_quota.json'
        self.qm = QuotaManager(self.test_file)
        # Clean up before test
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        # Clean up after test
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_initial_check(self):
        self.assertTrue(self.qm.check_quota('user1'))

    def test_usage_tracking(self):
        self.qm.add_usage('user1', 1024) # 1KB
        self.assertTrue(self.qm.check_quota('user1'))
        
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['user1']['bytes_used'], 1024)

    def test_quota_exceeded(self):
        self.qm.add_usage('user1', DAILY_LIMIT)
        # Now it should be equal to limit. Next check is "bytes_used < limit".
        # If used == limit, then used < limit is False.
        self.assertFalse(self.qm.check_quota('user1'))
        
        # Add one more byte just to be sure
        self.qm.add_usage('user1', 1)
        self.assertFalse(self.qm.check_quota('user1'))

    def test_daily_reset(self):
        # Simulate usage yesterday
        self.qm.data['user1'] = {'date': '2020-01-01', 'bytes_used': DAILY_LIMIT + 100}
        self.qm._save()
        
        # Today is definitely not 2020-01-01, so it should reset
        self.assertTrue(self.qm.check_quota('user1'))
        
        # Verify reset in file
        with open(self.test_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['user1']['bytes_used'], 0)

if __name__ == '__main__':
    unittest.main()
