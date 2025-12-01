import unittest
from app import app

class TestCSRF(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Enable CSRF for testing
        app.config['WTF_CSRF_ENABLED'] = True

    def test_csrf_protected_endpoint_fail(self):
        """Test that POST request without CSRF token fails."""
        # Try to post to /api/download without token
        res = self.app.post('/api/download', json={'url': 'https://example.com'})
        # Should return 400 (Bad Request) - standard Flask-WTF behavior
        # Or 403 depending on config, usually 400 'The CSRF token is missing.'
        self.assertIn(res.status_code, [400, 403])
        self.assertIn(b'CSRF', res.data)

    def test_csrf_token_generation(self):
        """Test that index page contains CSRF token."""
        res = self.app.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'name="csrf-token"', res.data)

if __name__ == '__main__':
    unittest.main()
