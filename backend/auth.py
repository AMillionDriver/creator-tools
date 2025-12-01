import os
from functools import wraps
from flask import request, jsonify

# Load API Key from environment
API_KEY = os.environ.get('API_KEY')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If API_KEY is NOT set in the environment, we must still enforce that it's required for this decorator.
        # This prevents accidental public exposure of endpoints marked as protected.
        if API_KEY is None:
            # For simplicity, if API_KEY is not configured, we'll indicate authentication is not available/configured.
            # In a production setup, this would ideally raise an error on app startup or require configuration.
            return jsonify({"error": "Authentication not configured: API_KEY environment variable is missing"}), 500

        key = request.headers.get('X-API-Key')
        if key and key == API_KEY:
            return f(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorized: Invalid or missing API Key"}), 401
    return decorated_function
