import os
import subprocess
import re
import logging
from celery import Celery
from celery.signals import task_postrun
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

# Setup basic logging for the Celery worker
logging.basicConfig(level=logging.INFO)
celery_logger = logging.getLogger(__name__)

# --- Configuration ---
REDIS_BROKER_URL = os.environ.get('REDIS_BROKER_URL', 'redis://localhost:6379/0')
REDIS_BACKEND_URL = os.environ.get('REDIS_BACKEND_URL', 'redis://localhost:6379/1')

ARIA2C_PATH = os.environ.get('ARIA2C_PATH')
if not ARIA2C_PATH:
    celery_logger.error("ARIA2C_PATH not set in .env or environment variables. Downloads may fail.")

# FILE_EXPIRATION_TIME for consistency, though cleanup is in Flask app
FILE_EXPIRATION_TIME = int(os.environ.get('FILE_EXPIRATION_TIME', 3600)) 

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'downloads')


# Celery App Initialization
celery_app = Celery('download_tasks',
                    broker=REDIS_BROKER_URL,
                    backend=REDIS_BACKEND_URL)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Jakarta', # Or your desired timezone
    enable_utc=True,
)

# Ensure DOWNLOADS_DIR exists for the worker
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Helper function (copied from app.py)
def downloaded_files_for_task(task_id_prefix):
    # This might need adjustment if task_id != file_prefix
    return any(f.startswith(task_id_prefix) for f in os.listdir(DOWNLOADS_DIR))


@celery_app.task(bind=True)
def download_video_task(self, url, format_id, task_id, custom_filename=None):
    celery_logger.info(f"[{task_id}] Celery task started for URL: {url}, Custom Filename: {custom_filename}")
    
    # Sanitize custom_filename to prevent path traversal or other issues
    if custom_filename:
        # Remove any path separators and invalid characters
        sanitized_filename = re.sub(r'[\\/:*?"<>|]', '', custom_filename)
        # Add %(ext)s so yt-dlp can append the correct extension
        output_template = os.path.join(DOWNLOADS_DIR, f"{sanitized_filename}.%(ext)s")
    else:
        output_template = os.path.join(DOWNLOADS_DIR, f"{task_id}.%(ext)s")


    try:
        command = [
            "yt-dlp",
            "-f", format_id,
            "--external-downloader", ARIA2C_PATH,
            "--external-downloader-args", "-x 16 -s 16 -k 1M",
            "-o", output_template,
            url
        ]
        
        celery_logger.info(f"[{task_id}] Executing command: {' '.join(command)}")

        # Use subprocess.run for better stability on Windows
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        if process.returncode != 0:
            stderr_output = process.stderr
            error_message = "Download failed."
            details = stderr_output

            if "aria2c exited with code" in stderr_output:
                error_message = "Download gagal melalui aria2c."
            elif "ERROR: " in stderr_output:
                error_message = "Download gagal karena masalah yt-dlp."

            celery_logger.error(f"[{task_id}] Download process failed. Stderr: {stderr_output}")
            self.update_state(state='FAILURE', meta={'message': error_message, 'details': details})
            return {'status': 'Failed', 'message': error_message, 'details': details}
        
        # Check if downloaded file exists
        # We search for files starting with the task_id or sanitized filename if provided
        search_prefix = task_id
        if custom_filename:
             sanitized_filename = re.sub(r'[\\/:*?"<>|]', '', custom_filename)
             search_prefix = sanitized_filename

        # Refresh file list check
        found_files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(search_prefix)]
        
        if found_files:
            filename = found_files[0]
            celery_logger.info(f"[{task_id}] Download completed successfully: {filename}")
            return {'status': 'Completed', 'filename': filename, 'percentage': 100}
        else:
            error_message = 'Download process finished successfully but no file found.'
            celery_logger.error(f"[{task_id}] {error_message}")
            self.update_state(state='FAILURE', meta={'message': error_message})
            return {'status': 'Failed', 'message': error_message}

    except FileNotFoundError:
        error_msg = ("Executable yt-dlp atau aria2c tidak ditemukan. Pastikan sudah terinstal dan path benar. "
                     f"ARIA2C_PATH saat ini: {ARIA2C_PATH}")
        celery_logger.error(f"[{task_id}] FileNotFoundError: {error_msg}")
        self.update_state(state='FAILURE', meta={'message': error_msg})
        return {'status': 'Failed', 'message': error_msg}
    except Exception as e:
        error_msg = f"Unexpected error during download: {str(e)}"
        celery_logger.error(f"[{task_id}] {error_msg}", exc_info=True)
        self.update_state(state='FAILURE', meta={'message': error_msg, 'details': str(e)})
        return {'status': 'Failed', 'message': error_msg, 'details': str(e)}