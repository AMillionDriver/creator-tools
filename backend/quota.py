import os
import redis
import json
from datetime import datetime

DAILY_LIMIT = 15 * 1024 * 1024 * 1024 # 15 GB
QUOTA_KEY_PREFIX = 'download_quota:'

class QuotaManager:
    def __init__(self):
        redis_url = os.environ.get('REDIS_BROKER_URL', 'redis://localhost:6379/0')
        # Use decode_responses=True to get strings instead of bytes
        self.r = redis.from_url(redis_url, decode_responses=True)

    def _get_today_str(self):
        return datetime.now().strftime('%Y-%m-%d')

    def check_quota(self, user_id):
        """Returns True if user is within quota, False otherwise."""
        today = self._get_today_str()
        key = f"{QUOTA_KEY_PREFIX}{user_id}"
        
        # Get current usage data from Redis
        user_data_str = self.r.hget(key, 'data')
        if user_data_str:
            user_data = json.loads(user_data_str)
        else:
            user_data = {'date': today, 'bytes_used': 0}

        # Reset if new day
        if user_data.get('date') != today:
            user_data = {'date': today, 'bytes_used': 0}
            self.r.hset(key, 'data', json.dumps(user_data)) # Update Redis
        
        return user_data['bytes_used'] < DAILY_LIMIT

    def add_usage(self, user_id, bytes_used):
        """Adds bytes to user's daily usage."""
        today = self._get_today_str()
        key = f"{QUOTA_KEY_PREFIX}{user_id}"
        
        # Get current usage data from Redis
        user_data_str = self.r.hget(key, 'data')
        if user_data_str:
            user_data = json.loads(user_data_str)
        else:
            user_data = {'date': today, 'bytes_used': 0}

        # Reset if new day (edge case where check wasn't called or day changed during dl)
        if user_data.get('date') != today:
            user_data = {'date': today, 'bytes_used': 0}
        
        user_data['bytes_used'] += bytes_used
        self.r.hset(key, 'data', json.dumps(user_data)) # Update Redis

    def get_remaining(self, user_id):
        today = self._get_today_str()
        key = f"{QUOTA_KEY_PREFIX}{user_id}"
        
        user_data_str = self.r.hget(key, 'data')
        if user_data_str:
            user_data = json.loads(user_data_str)
        else:
            user_data = {'date': today, 'bytes_used': 0}
        
        if user_data.get('date') != today:
            return DAILY_LIMIT
            
        return max(0, DAILY_LIMIT - user_data['bytes_used'])
