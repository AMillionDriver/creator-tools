import redis
import os
from dotenv import load_dotenv

# Load .env manually to get configs
load_dotenv(os.path.join('backend', '.env'))

host = os.environ.get('REDIS_CACHE_HOST', 'localhost')
port = int(os.environ.get('REDIS_CACHE_PORT', 6379))

print(f"Connecting to Redis at {host}:{port}...")

try:
    r = redis.Redis(host=host, port=port)
    r.flushall()
    print("✅ Success! All Redis databases have been flushed (cleared).")
except Exception as e:
    print(f"❌ Error: {e}")
