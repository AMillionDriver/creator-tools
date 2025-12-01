import unittest
from unittest.mock import patch, MagicMock
from app import app

class TestRecaptcha(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('app.requests.post')
    @patch.dict('os.environ', {'RECAPTCHA_SECRET_KEY': 'dummy_secret', 'RECAPTCHA_SITE_KEY': 'dummy_site'})
    def test_missing_captcha(self, mock_post):
        # Need to reload app config effectively or patch the variable directly since it's loaded at module level
        # But for this simple test, we assume the verified logic is inside the route function which checks the global var.
        # Wait, app.py loads env vars at top level. Patching os.environ here might be too late if not reloaded.
        # However, let's patch the app.RECAPTCHA_SECRET_KEY directly if possible, or relying on the fact that we modified app.py to use os.environ.get() ? 
        # In my code I assigned RECAPTCHA_SECRET_KEY = os.environ.get(...) at top level. 
        # So I need to patch that module level variable.
        
        with patch('app.RECAPTCHA_SECRET_KEY', 'dummy_secret'):
            payload = {
                'url': 'https://youtube.com/watch?v=123', 
                'format_id': '18',
                # 'g-recaptcha-response': missing
            }
            # We also need to bypass is_safe_url and other checks to reach captcha check
            # Mocking is_safe_url might be needed or use a real safe url.
            
            res = self.app.post('/api/process-video', json=payload)
            self.assertEqual(res.status_code, 400)
            self.assertIn(b'Please complete the captcha', res.data)

    @patch('app.requests.post')
    def test_valid_captcha(self, mock_post):
        # Mock Google response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'success': True}
        mock_post.return_value = mock_resp

        with patch('app.RECAPTCHA_SECRET_KEY', 'dummy_secret'):
            # We need to bypass quota check too if we want 200, or just check that it PASSED captcha check.
            # If captcha passes, it proceeds to safe url check.
            
            payload = {
                'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 
                'format_id': '18',
                'g-recaptcha-response': 'valid_token'
            }
            
            # We expect it to proceed. It might fail on quota or threading if not mocked, 
            # but definitely NOT "Please complete the captcha".
            
            # Let's just check it doesn't return 400 Captcha error.
            res = self.app.post('/api/process-video', json=payload)
            self.assertNotIn(b'Please complete the captcha', res.data)
            self.assertNotIn(b'Captcha verification failed', res.data)

if __name__ == '__main__':
    unittest.main()
