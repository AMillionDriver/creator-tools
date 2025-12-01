import os
from functools import wraps
from flask import request, jsonify

# Load API Key from environment
API_KEY = os.environ.get('API_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If no API Key is set in env, we might allow everything or block everything.
        # Security-first: if explicitly asked for auth, we should block if no key is provided.
        # However, for a local tool, if API_KEY is missing, maybe we skip?
        # Let's enforce it if it exists. If not, assume open (or setup guide needed).
        # But prompt says "Add authentication".
        if API_KEY:
            key = request.headers.get('X-API-Key')
            if key and key == API_KEY:
                return f(*args, **kwargs)
            else:
                return jsonify({"error": "Unauthorized: Invalid or missing API Key"}), 401
        return f(*args, **kwargs)
    return decorated_function
