from celery_worker import download_video_task
import time

print("Sending test task...")
# Kirim task dummy (URL ngasal aja dulu, kita cuma mau liat worker bereaksi atau nggak)
task = download_video_task.delay("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "best", "test-task-123")
print(f"Task sent! ID: {task.id}")

print("Checking status...")
time.sleep(2)
print(f"Status: {task.status}")
