import unittest
import os
from app import app, SAFE_EXTENSIONS

class TestFileServingSecurity(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_safe_extensions(self):
        """Test that safe extensions are allowed."""
        # We are not actually downloading files, just checking the extension logic.
        # Since send_from_directory checks for file existence, we expect 404 for safe but missing files,
        # but 403 for unsafe files regardless of existence (if check happens first).
        
        # Let's rely on the fact that our 403 check happens BEFORE send_from_directory.
        
        safe_files = [
            "video.mp4", "song.mp3", "image.jpg", "movie.mkv", "audio.flac"
        ]
        for filename in safe_files:
            response = self.app.get(f'/downloads/{filename}')
            # Should NOT be 403. It might be 404 because file doesn't exist, which is fine.
            self.assertNotEqual(response.status_code, 403, f"Safe file {filename} was blocked")

    def test_unsafe_extensions(self):
        """Test that unsafe extensions are blocked."""
        unsafe_files = [
            "virus.exe", "script.sh", "config.php", "win.bat", "macro.docm", "unknown.xyz"
        ]
        for filename in unsafe_files:
            response = self.app.get(f'/downloads/{filename}')
            self.assertEqual(response.status_code, 403, f"Unsafe file {filename} was NOT blocked")
            self.assertIn("File type not allowed", response.get_json()['error'])

    def test_double_extension_bypass(self):
        """Test attempts to bypass using double extensions."""
        # Often servers are tricked by file.jpg.exe.
        # Our logic splits by the last dot.
        unsafe_bypass = [
            "safe.jpg.exe",
            "video.mp4.bat",
            "data.json" # json is not in safe list
        ]
        for filename in unsafe_bypass:
            response = self.app.get(f'/downloads/{filename}')
            self.assertEqual(response.status_code, 403, f"Bypass attempt {filename} succeeded")

if __name__ == '__main__':
    unittest.main()
