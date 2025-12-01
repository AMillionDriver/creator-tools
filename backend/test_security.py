import unittest
from utils import is_safe_url

class TestUrlSecurity(unittest.TestCase):
    def test_allowed_domains(self):
        allowed = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=123",
            "https://www.tiktok.com/@user/video/1234567890",
            "https://vm.tiktok.com/ZM8G",
            "https://www.instagram.com/p/C12345/",
            "https://soundcloud.com/artist/track",
            "https://www.facebook.com/watch/?v=123",
            "https://fb.watch/123",
            "https://twitter.com/user/status/123",
            "https://x.com/user/status/123"
        ]
        for url in allowed:
            self.assertTrue(is_safe_url(url), f"Should be allowed: {url}")

    def test_blocked_domains(self):
        blocked = [
            "https://google.com",
            "http://example.com",
            "https://malicious.site/video.mp4",
            "ftp://youtube.com/file", # Wrong scheme
            "file:///etc/passwd", # Local file
            "http://localhost:5000", # Localhost
            "http://127.0.0.1/admin", # Local IP
            "https://192.168.1.1/router", # Local Network
            "javascript:alert(1)", # Javascript scheme
            "https://youtube.com.evil.com", # Subdomain phishing
            "https://evil-youtube.com", # Typosquatting
        ]
        for url in blocked:
            self.assertFalse(is_safe_url(url), f"Should be blocked: {url}")

    def test_malformed_urls(self):
        malformed = [
            "",
            None,
            "not_a_url",
            "youtube.com", # Missing scheme
        ]
        for url in malformed:
            self.assertFalse(is_safe_url(url), f"Should be invalid: {url}")

if __name__ == '__main__':
    unittest.main()
