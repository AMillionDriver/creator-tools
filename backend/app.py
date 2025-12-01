import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
import requests
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from utils import is_safe_url
from auth import require_api_key, API_KEY
from quota import QuotaManager

load_dotenv()

# Recaptcha Config
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')
RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')

# Konfigurasi logging
logging.basicConfig(
    filename='flask_app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static',
    static_url_path='/static'
)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
CORS(app)
csrf = CSRFProtect(app)

# Setup Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get('REDIS_BROKER_URL', 'redis://localhost:6379/0') # Use Redis for persistent storage
)

# --- Konfigurasi ---
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

SAFE_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.jpg', '.jpeg', '.png', '.webp'}
MAX_FILESIZE = 5 * 1024 * 1024 * 1024 # 5GB
TIMEOUT_SECONDS = 3600 # 1 Hour

quota_manager = QuotaManager()

ARIA2C_PATH = os.environ.get('ARIA2C_PATH')
# Fix path separator if needed
if ARIA2C_PATH:
    ARIA2C_PATH = ARIA2C_PATH.replace('\\', '/')

# Semaphore to limit concurrent downloads
MAX_CONCURRENT_DOWNLOADS = 3 # Example limit
download_semaphore = threading.BoundedSemaphore(value=MAX_CONCURRENT_DOWNLOADS)


# --- In-Memory Status Storage ---
# Menyimpan status download yang sedang berjalan
# Format: { 'task_id': { 'status': '...', 'percentage': 0, 'filename': '...' } }
download_tasks = {}

def run_download_thread(task_id, url, format_id, user_identifier, custom_filename=None):
    """Fungsi ini berjalan di thread terpisah"""
    print(f"[{task_id}] Thread started for URL: {url}")
    
    download_tasks[task_id] = {
        'status': 'Starting...', 
        'percentage': 0,
        'message': 'Initializing download...'
    }

    # Acquire semaphore
    # The actual acquire happens in the calling function, this thread will just execute.

    # Sanitize filename
    if custom_filename:
        sanitized_filename = re.sub(r'[\\/:*?"<>|]', '', custom_filename)
        output_template = os.path.join(DOWNLOADS_DIR, f"{sanitized_filename}.%(ext)s")
    else:
        output_template = os.path.join(DOWNLOADS_DIR, f"{task_id}.%(ext)s")

    command = [
        "yt-dlp",
        "-f", format_id,
        "--max-filesize", "5G", # Enforce max size at downloader level
        "-o", output_template,
        # Kita matikan aria2c sementara agar progress bar yt-dlp lebih mudah diparsing
        # Jika ingin pakai aria2c, parsing logikanya harus disesuaikan lagi
        url
    ]
    
    # DEBUG PRINT COMMAND
    print(f"[{task_id}] EXECUTING CMD: {' '.join(command)}")

    start_time = time.time()
    process = None

    try:
        # Jalankan proses dan baca output real-time
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Gabung stderr ke stdout agar bisa dibaca
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1, # Line buffered
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        last_lines = [] # Simpan output terakhir untuk debug error

        while True:
            # Check for timeout
            if time.time() - start_time > TIMEOUT_SECONDS:
                process.kill()
                raise TimeoutError("Download timed out (exceeded 1 hour)")

            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if not line:
                time.sleep(0.1) # prevent tight loop if no output temporarily
                continue
            
            line = line.strip()
            # Print ke terminal backend agar admin bisa baca lognya
            print(f"[{task_id}] yt-dlp: {line}")
            
            # Simpan 5 baris terakhir
            last_lines.append(line)
            if len(last_lines) > 5:
                last_lines.pop(0)
            
            # Parsing Progress yt-dlp
            # Contoh: [download]  45.0% of 10.00MiB at 2.50MiB/s ETA 00:05
            match = re.search(r'\[download\]\s+(\d+\.\d+)%', line)
            if match:
                percent = float(match.group(1))
                download_tasks[task_id]['status'] = 'Downloading'
                download_tasks[task_id]['percentage'] = percent
                download_tasks[task_id]['message'] = f"{percent}% completed"
            
        if process.returncode == 0:
            # Cari file hasil download
            search_prefix = task_id
            if custom_filename:
                 search_prefix = re.sub(r'[\\/:*?"<>|]', '', custom_filename)

            # Refresh file list
            files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(search_prefix)]
            if files:
                final_filename = files[0]
                file_path = os.path.join(DOWNLOADS_DIR, final_filename)
                file_size = os.path.getsize(file_path)

                # Update Quota
                quota_manager.add_usage(user_identifier, file_size)

                download_tasks[task_id]['status'] = 'Completed'
                download_tasks[task_id]['percentage'] = 100
                download_tasks[task_id]['filename'] = final_filename
                download_tasks[task_id]['message'] = 'Download Finished!'
            else:
                download_tasks[task_id]['status'] = 'Failed'
                download_tasks[task_id]['message'] = 'File not found after download.'
        else:
            # Ambil pesan error dari output terakhir
            error_details = " | ".join(last_lines)
            # Check for specific max filesize error from yt-dlp
            if "File is larger than" in error_details or "Abort" in error_details: 
                 error_details = "File exceeded maximum allowed size (5GB)."

            download_tasks[task_id]['status'] = 'Failed'
            download_tasks[task_id]['message'] = f"Error: {error_details}"

    except Exception as e:
        print(f"[{task_id}] Error: {e}")
        if process and process.poll() is None:
            process.kill()
        download_tasks[task_id]['status'] = 'Failed'
        download_tasks[task_id]['message'] = str(e)
    finally:
        # Always release the semaphore
        download_semaphore.release()
        print(f"[{task_id}] Semaphore released.")


@app.route('/')
def index():
    return render_template('index.html', recaptcha_site_key=RECAPTCHA_SITE_KEY)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/download', methods=['POST'])
@limiter.limit("5 per minute")
def download_info():
    """Mengambil info video (Thumbnail, Judul, Format)"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not is_safe_url(url):
        return jsonify({"error": "Invalid or restricted URL domain"}), 400

    try:
        command = ["yt-dlp", "--dump-json", "--no-warnings", url]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        video_info = json.loads(result.stdout)

        formats = video_info.get('formats', [])
        relevant_formats = []
        
        # Ambil format yang relevan (Video+Audio atau Video Only)
        for f in formats:
            ext = f.get('ext')
            if ext not in ['mp4', 'mkv', 'webm']:
                continue
            
            format_note = f.get('format_note', '')
            resolution = f.get('resolution', 'N/A')
            filesize = f.get('filesize')
            
            # Sederhanakan data untuk frontend
            relevant_formats.append({
                'format_id': f['format_id'],
                'ext': ext,
                'resolution': resolution,
                'note': format_note,
                'filesize': filesize,
                # Kita tidak butuh URL langsung lagi karena download lewat backend
            })
        
        # Sortir format (opsional, misal dari resolusi tertinggi)
        relevant_formats.reverse()

        return jsonify({
            "title": video_info.get('title', 'Untitled'),
            "thumbnail": video_info.get('thumbnail'),
            "uploader": video_info.get('uploader', 'Unknown Creator'),
            "view_count": video_info.get('view_count', 0),
            "like_count": video_info.get('like_count', 0),
            "comment_count": video_info.get('comment_count', 0),
            "duration": video_info.get('duration', 0),
            "categories": video_info.get('categories', []),
            "upload_date": video_info.get('upload_date', None),
            "formats": relevant_formats
        })

    except Exception as e:
        return jsonify({"error": "Failed to fetch video info", "details": str(e)}), 500


@app.route('/api/process-video', methods=['POST'])
@limiter.limit("3 per minute")
def process_video():
    """Memulai proses download di background thread"""
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')
    filename = data.get('filename')

    # Identify User for Quota (Now primarily by IP, as API key is not sent from frontend)
    user_identifier = request.remote_addr

    # Check Quota
    if not quota_manager.check_quota(user_identifier):
        return jsonify({"error": "Daily download quota exceeded (15GB limit)."}), 429

    # DEBUG PRINT
    print(f"\n[REQUEST] Process Video: URL={url}")
    print(f"[REQUEST] Requested Format ID: {format_id}")

    if not url or not format_id:
        return jsonify({"error": "Missing data"}), 400

    # Verify reCAPTCHA
    captcha_response = data.get('g-recaptcha-response')
    if RECAPTCHA_SECRET_KEY: # Only verify if key is configured
        if not captcha_response:
             return jsonify({"error": "Please complete the captcha."}), 400
        
        verify_payload = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': captcha_response,
            'remoteip': request.remote_addr
        }
        try:
            verify_req = requests.post('https://www.google.com/recaptcha/api/siteverify', data=verify_payload, timeout=10)
            verify_resp = verify_req.json()
            if not verify_resp.get('success'):
                return jsonify({"error": "Captcha verification failed. Please try again."}), 400
        except Exception as e:
             print(f"Captcha Error: {e}")
             # Fail open or closed? Safe to fail closed.
             return jsonify({"error": "Captcha verification error."}), 500

    if not is_safe_url(url):
        return jsonify({"error": "Invalid or restricted URL domain"}), 400

    task_id = str(uuid.uuid4())
    
    if not download_semaphore.acquire(blocking=False):
        return jsonify({"error": f"Too many concurrent downloads. Please wait for an active download to finish (max {MAX_CONCURRENT_DOWNLOADS})."}), 429

    # Jalankan thread
    thread = threading.Thread(target=run_download_thread, args=(task_id, url, format_id, user_identifier, filename))
    thread.daemon = True # Agar thread mati jika server mati
    thread.start()

    return jsonify({"task_id": task_id, "status": "started"})


@app.route('/api/status/<task_id>')
def get_status(task_id):
    """Cek status download dari memory"""
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({"status": "Not Found"}), 404
    
    response = {
        "status": task['status'],
        "percentage": task['percentage'],
        "message": task['message']
    }
    
    if task.get('filename'):
        response['download_link'] = f"/downloads/{task['filename']}"
        
    return jsonify(response)


@app.route('/downloads/<path:filename>')
def download_file(filename):
    # Security Check: Restrict file types to prevent malware distribution
    _, ext = os.path.splitext(filename)
    if ext.lower() not in SAFE_EXTENSIONS:
        return jsonify({"error": "File type not allowed"}), 403
        
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)