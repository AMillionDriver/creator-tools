import subprocess
import json

print("Testing yt-dlp execution...")
try:
    # Coba ambil info video pendek
    command = ["yt-dlp", "--dump-json", "--no-warnings", "https://www.youtube.com/watch?v=jNQXAC9IVRw"]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        encoding='utf-8'
    )
    print("✅ yt-dlp Success!")
    info = json.loads(result.stdout)
    print(f"Title: {info.get('title')}")
except FileNotFoundError:
    print("❌ yt-dlp NOT FOUND in PATH.")
except subprocess.CalledProcessError as e:
    print(f"❌ yt-dlp Failed with error:")
    print(e.stderr)
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
