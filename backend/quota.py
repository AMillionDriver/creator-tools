import json
import os
import time
from datetime import datetime

QUOTA_FILE = 'quota_tracker.json'
DAILY_LIMIT = 15 * 1024 * 1024 * 1024 # 15 GB

class QuotaManager:
    def __init__(self, filepath=QUOTA_FILE):
        self.filepath = filepath
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.data = json.load(f)
            except:
                self.data = {}
        else:
            self.data = {}

    def _save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f)

    def _get_today_str(self):
        return datetime.now().strftime('%Y-%m-%d')

    def check_quota(self, user_id):
        """Returns True if user is within quota, False otherwise."""
        self._load() # Reload to get latest
        today = self._get_today_str()
        user_data = self.data.get(user_id, {})
        
        # Reset if new day
        if user_data.get('date') != today:
            user_data = {'date': today, 'bytes_used': 0}
            self.data[user_id] = user_data
            self._save()
        
        return user_data['bytes_used'] < DAILY_LIMIT

    def add_usage(self, user_id, bytes_used):
        """Adds bytes to user's daily usage."""
        self._load()
        today = self._get_today_str()
        user_data = self.data.get(user_id, {'date': today, 'bytes_used': 0})

        # Reset if new day (edge case where check wasn't called or day changed during dl)
        if user_data.get('date') != today:
            user_data = {'date': today, 'bytes_used': 0}
        
        user_data['bytes_used'] += bytes_used
        self.data[user_id] = user_data
        self._save()

    def get_remaining(self, user_id):
        self._load()
        today = self._get_today_str()
        user_data = self.data.get(user_id, {'date': today, 'bytes_used': 0})
        
        if user_data.get('date') != today:
            return DAILY_LIMIT
            
        return max(0, DAILY_LIMIT - user_data['bytes_used'])
