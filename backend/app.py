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
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf
from urllib.parse import urlparse
from datetime import datetime

# Load environment variables from .env file
load_dotenv(dotenv_path='backend/.env')

# Recaptcha Config
RECAPTCHA_SITE_KEY = os.environ.get('RECAPTCHA_SITE_KEY')
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY')

# Configure logging
logging.basicConfig(
    filename='flask_app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Flask application setup
app = Flask(
    __name__,
    template_folder='./frontend/templates',
    static_folder='./frontend/static',
    static_url_path='/static'
)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')

# Basic CORS configuration for local development.
CORS(app)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Set up Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://" 
)

# --- Application-specific Configuration ---
DOWNLOADS_DIR = './backend/downloads'
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

SAFE_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.flac', '.jpg', '.jpeg', '.png', '.webp'}
MAX_FILESIZE = 5 * 1024 * 1024 * 1024
TIMEOUT_SECONDS = 3600

# Quota Manager implementation using a local JSON file.
class QuotaManager:
    def __init__(self, filepath='quota_tracker.json'):
        self.filepath = filepath
        self.DAILY_LIMIT = 15 * 1024 * 1024 * 1024 # 15 GB
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                self.data = {} 
        else:
            self.data = {}

    def _save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f)

    def _get_today_date_str(self):
        return datetime.now().strftime('%Y-%m-%d')

    def check_quota(self, user_id):
        self._load()
        today_date = self._get_today_date_str()
        user_data = self.data.get(user_id, {})

        if user_data.get('date') != today_date:
            user_data = {'date': today_date, 'bytes_used': 0}
            self.data[user_id] = user_data
            self._save()
        
        return user_data['bytes_used'] < self.DAILY_LIMIT

    def add_usage(self, user_id, bytes_used):
        self._load()
        today_date = self._get_today_date_str()
        user_data = self.data.get(user_id, {'date': today_date, 'bytes_used': 0})

        if user_data.get('date') != today_date:
            user_data = {'date': today_date, 'bytes_used': 0}
        
        user_data['bytes_used'] += bytes_used
        self.data[user_id] = user_data
        self._save()

    def get_remaining(self, user_id):
        self._load()
        today_date = self._get_today_date_str()
        user_data = self.data.get(user_id, {'date': today_date, 'bytes_used': 0})
        
        if user_data.get('date') != today_date:
            return self.DAILY_LIMIT
        
        return max(0, self.DAILY_LIMIT - user_data['bytes_used'])
    
quota_manager = QuotaManager(filepath=os.path.join(DOWNLOADS_DIR, 'quota_tracker.json'))

ARIA2C_PATH = os.environ.get('ARIA2C_PATH', 'aria2c')

download_tasks = {}

MAX_CONCURRENT_DOWNLOADS = 3
download_semaphore = threading.BoundedSemaphore(value=MAX_CONCURRENT_DOWNLOADS)

ALLOWED_DOMAINS = [
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com',
    'instagram.com', 'www.instagram.com',
    'soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com',
    'facebook.com', 'www.facebook.com', 'web.facebook.com', 'm.facebook.com', 'fb.watch',
    'twitter.com', 'www.twitter.com', 'mobile.twitter.com',
    'x.com', 'www.x.com'
]

def is_safe_url(url):
    if not url:
        return False
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ('http', 'https'):
            return False
        
        domain = parsed_url.netloc.lower()
        if ':' in domain:
            domain = domain.split(':')[0]
            
        if domain in ALLOWED_DOMAINS:
            return True
            
        return False
    except Exception:
        return False

def run_download_thread(task_id, url, format_id, user_identifier="unknown", custom_filename=None):
    app.logger.info(f"[{task_id}] Thread started for URL: {url}")
    download_tasks[task_id] = {
        'status': 'Starting...', 
        'percentage': 0,
        'message': 'Initializing download...'
    }

    process = None
    try:
        if not download_semaphore.acquire(blocking=False):
            download_tasks[task_id]['status'] = 'Failed'
            download_tasks[task_id]['message'] = f"Max concurrent downloads ({MAX_CONCURRENT_DOWNLOADS}) reached. Please try again later."
            return 

        if custom_filename:
            sanitized_filename = re.sub(r'[\\/:*?"<>|]', '', custom_filename)
            output_template = os.path.join(DOWNLOADS_DIR, f"{sanitized_filename}.%(ext)s")
        else:
            output_template = os.path.join(DOWNLOADS_DIR, f"{task_id}.%(ext)s")

        command = [
            "yt-dlp",
            "-f", format_id,
            "--max-filesize", f"{MAX_FILESIZE // (1024 * 1024 * 1024)}G",
            "-o", output_template,
            url
        ]
        
        app.logger.info(f"[{task_id}] EXECUTING CMD: {' '.join(command)}")

        start_time = time.time()
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1, 
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        last_lines = []

        while True:
            if time.time() - start_time > TIMEOUT_SECONDS:
                if process.poll() is None:
                    process.kill()
                raise TimeoutError("Download timed out (exceeded 1 hour)")

            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if not line:
                time.sleep(0.1)
                continue
            
            line = line.strip()
            app.logger.info(f"[{task_id}] yt-dlp: {line}")
            
            last_lines.append(line)
            if len(last_lines) > 5:
                last_lines.pop(0)
            
            match = re.search(r'download]  (\d+\.\d+)%', line)
            if match:
                percent = float(match.group(1))
                download_tasks[task_id]['status'] = 'Downloading'
                download_tasks[task_id]['percentage'] = percent
                download_tasks[task_id]['message'] = f"{percent}% completed"
            
        process.wait()

        if process.returncode == 0:
            search_prefix = task_id
            if custom_filename:
                search_prefix = re.sub(r'[\\/:*?"<>|]', '', custom_filename)

            files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(search_prefix)]
            if files:
                final_filename = files[0]
                file_path = os.path.join(DOWNLOADS_DIR, final_filename)
                
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    quota_manager.add_usage(user_identifier, file_size)

                    download_tasks[task_id]['status'] = 'Completed'
                    download_tasks[task_id]['percentage'] = 100
                    download_tasks[task_id]['filename'] = final_filename
                    download_tasks[task_id]['message'] = 'Download Finished!'
                else:
                    download_tasks[task_id]['status'] = 'Failed'
                    download_tasks[task_id]['message'] = 'Download finished, but file not found on disk.'
            else:
                download_tasks[task_id]['status'] = 'Failed'
                download_tasks[task_id]['message'] = 'File not found after download.'
        else:
            error_msg = " | ".join(last_lines)
            if "File is larger than" in error_msg or "Abort" in error_msg: 
                error_msg = "File exceeded maximum allowed size (5GB)."
            download_tasks[task_id]['status'] = 'Failed'
            download_tasks[task_id]['message'] = f"Error: {error_msg}"

    except Exception as e:
        app.logger.error(f"[{task_id}] Subprocess error: {e}", exc_info=True)
        if process and process.poll() is None:
            process.kill()
        download_tasks[task_id]['status'] = 'Failed'
        download_tasks[task_id]['message'] = str(e)
    finally:
        download_semaphore.release()
        app.logger.info(f"[{task_id}] Semaphore released. Available: {download_semaphore._value}")


@app.route('/')
def index():
    return render_template('index.html', recaptcha_site_key=RECAPTCHA_SITE_KEY, csrf_token=generate_csrf())

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/download', methods=['POST'])
@limiter.limit("5 per minute")
@csrf.exempt # Exemption explained below. 
def download_info():
    """Pulls video information from a given URL, validates it, and returns relevant formats.
    This endpoint is exempt from CSRF protection as it's typically a GET-like operation
    (even if using POST for body data) that does not modify server state.
    """
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    if not is_safe_url(url):
        return jsonify({"error": "Invalid or restricted URL domain"}), 400

    try:
        command_ytdesc = ["yt-dlp", "--dump-json", "--no-warnings", url]
        result = subprocess.run(command_ytdesc, capture_output=True, text=True, check=True, encoding='utf-8')
        video_info = json.loads(result.stdout)

        formats = video_info.get('formats', [])
        relevant_formats = []
        
        for f in formats:
            ext = f.get('ext')
            if ext not in SAFE_EXTENSIONS: # Use established SAFE_EXTENSIONS for filtering
                continue
            
            resolution = f.get('resolution')
            if not resolution or resolution == '0x0':
                resolution = 'N/A'

            filesize = f.get('filesize')
            format_id_str = f.get('format_id')
            
            relevant_formats.append({
                'format_id': format_id_str,
                'ext': ext,
                'priority': f.get('preference', 0) if f.get('preference') is not None else 0, # Add priority for sorting
                'resolution': resolution,
                'note': f.get('format_note', ''),
                'filesize': filesize,
            })
        
        # Sort formats: by priority (desc), resolution (desc), then file size (desc)
        def sort_key(f):
            res_val = 0
            if f['resolution'] != 'N/A':
                try:
                    res_val = int(f['resolution'].split('x')[0])
                except ValueError:
                    pass
            return (f['priority'], res_val, f['filesize'] or 0)
        
        relevant_formats.sort(key=sort_key, reverse=True)

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

    except subprocess.CalledProcessError as e:
        app.logger.error(f"Failed to fetch video info for URL {url}: {e.stderr}")
        return jsonify({"error": "Failed to fetch video info", "details": e.stderr}), 500
    except json.JSONDecodeError:
        app.logger.error(f"Failed to parse video info for URL {url}. Raw output: {result.stdout}")
        return jsonify({"error": "Failed to parse video info from yt-dlp"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching video info for URL {url}: {e}")
        return jsonify({"error": "Failed to fetch video info", "details": str(e)}), 500


@app.route('/api/process-video', methods=['POST'])
@limiter.limit("3 per minute")
def process_video():
    """Memulai proses download di background thread"""
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')
    filename = data.get('filename')

    # Validate CSRF token
    if not validate_csrf(request.headers.get('X-CSRFToken')):
        return jsonify({"error": "CSRF token missing or incorrect"}), 403

    user_identifier = request.remote_addr

    if not quota_manager.check_quota(user_identifier):
        return jsonify({"error": "Daily download quota exceeded (15GB limit)."}), 429

    if not url or not format_id:
        return jsonify({"error": "Missing data"}), 400

    # Verify reCAPTCHA
    captcha_response = data.get('g-recaptcha-response')
    if RECAPTCHA_SECRET_KEY:
        if not captcha_response:
             return jsonify({"error": "Please complete the captcha."}),
 400
        
        verify_payload = {
            'secret': RECAPTCHA_SECRET_KEY,
            'response': captcha_response,
            'remoteip': request.remote_addr
        }
        try:
            verify_req = requests.post('https://www.google.com/recaptcha/api/siteverify', data=verify_payload, timeout=10)
            verify_resp = verify_req.json()
            if not verify_resp.get('success'):
                app.logger.warning(f"Failed Captcha verification for {user_identifier}: {verify_resp.get('error-codes')}")
                return jsonify({"error": "Captcha verification failed. Please try again."}),
 400
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Captcha verification request error: {e}")
            return jsonify({"error": "Captcha verification service unavailable."}),
 500

    if not is_safe_url(url):
        return jsonify({"error": "Invalid or restricted URL domain"}), 400

    task_id = str(uuid.uuid4())
    
    if not download_semaphore.acquire(blocking=False):
        return jsonify({"error": f"Too many concurrent downloads. Please wait for an active download to finish (max {MAX_CONCURRENT_DOWNLOADS})."}), 429

    thread = threading.Thread(target=run_download_thread, args=(task_id, url, format_id, user_identifier, filename))
    thread.daemon = True 
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
    """Serves downloaded files after checking their extensions for safety."""
    if not re.match(r"^[a-zA-Z0-9_\-\.]+", filename):
        return jsonify({"error": "Invalid filename"}), 400

    _, ext = os.path.splitext(filename)
    if ext.lower() not in SAFE_EXTENSIONS:
        return jsonify({"error": "File type not allowed"}), 403
        
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
