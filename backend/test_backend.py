import json
import urllib.request

# Data yang akan dikirim
post_data = {
    "url": "https://www.facebook.com/watch/?v=284023933944537"
}
# Encode data ke format bytes
post_data_encoded = json.dumps(post_data).encode('utf-8')

# Buat request
req = urllib.request.Request(
    'http://127.0.0.1:5000/api/download',
    data=post_data_encoded,
    headers={'Content-Type': 'application/json'}
)

try:
    # Kirim request dan baca responsenya
    with urllib.request.urlopen(req) as response:
        response_body = response.read().decode('utf-8')
        print(response_body)
except Exception as e:
    print(f"Error: {e}")
