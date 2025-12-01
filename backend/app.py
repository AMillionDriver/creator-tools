import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')

# Allow CORS with credentials (needed for CSRF cookie)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}}) 

csrf = CSRFProtect(app)

# ... rate limiter ...

@app.route('/api/handshake', methods=['GET'])
@limiter.limit("10 per minute")
def handshake():
    """
    Endpoint for frontend to get CSRF token and Config
    """
    token = generate_csrf()
    return jsonify({
        "csrf_token": token,
        "recaptcha_site_key": RECAPTCHA_SITE_KEY
    })

@app.route('/')
def index():
    return jsonify({"status": "online", "message": "Backend is running"})

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