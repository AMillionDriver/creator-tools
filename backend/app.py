import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

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
CORS(app)

# --- Konfigurasi ---
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

ARIA2C_PATH = os.environ.get('ARIA2C_PATH')
# Fix path separator if needed
if ARIA2C_PATH:
    ARIA2C_PATH = ARIA2C_PATH.replace('\\', '/')

# --- In-Memory Status Storage ---
# Menyimpan status download yang sedang berjalan
# Format: { 'task_id': { 'status': '...', 'percentage': 0, 'filename': '...' } }
download_tasks = {}

def run_download_thread(task_id, url, format_id, custom_filename=None):
    """Fungsi ini berjalan di thread terpisah"""
    print(f"[{task_id}] Thread started for URL: {url}")
    
    download_tasks[task_id] = {
        'status': 'Starting...', 
        'percentage': 0,
        'message': 'Initializing download...'
    }

    # Sanitize filename
    if custom_filename:
        sanitized_filename = re.sub(r'[\\/:*?"<>|]', '', custom_filename)
        output_template = os.path.join(DOWNLOADS_DIR, f"{sanitized_filename}.%(ext)s")
    else:
        output_template = os.path.join(DOWNLOADS_DIR, f"{task_id}.%(ext)s")

    command = [
        "yt-dlp",
        "-f", format_id,
        "-o", output_template,
        # Kita matikan aria2c sementara agar progress bar yt-dlp lebih mudah diparsing
        # Jika ingin pakai aria2c, parsing logikanya harus disesuaikan lagi
        url
    ]
    
    # DEBUG PRINT COMMAND
    print(f"[{task_id}] EXECUTING CMD: {' '.join(command)}")

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

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
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
            
        process.wait()

        if process.returncode == 0:
            # Cari file hasil download
            search_prefix = task_id
            if custom_filename:
                 search_prefix = re.sub(r'[\\/:*?"<>|]', '', custom_filename)

            # Refresh file list
            files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(search_prefix)]
            if files:
                final_filename = files[0]
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
            download_tasks[task_id]['status'] = 'Failed'
            download_tasks[task_id]['message'] = f"Error: {error_details}"

    except Exception as e:
        print(f"[{task_id}] Error: {e}")
        download_tasks[task_id]['status'] = 'Failed'
        download_tasks[task_id]['message'] = str(e)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/download', methods=['POST'])
def download_info():
    """Mengambil info video (Thumbnail, Judul, Format)"""
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

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
def process_video():
    """Memulai proses download di background thread"""
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')
    filename = data.get('filename')

    # DEBUG PRINT
    print(f"\n[REQUEST] Process Video: URL={url}")
    print(f"[REQUEST] Requested Format ID: {format_id}")

    if not url or not format_id:
        return jsonify({"error": "Missing data"}), 400

    task_id = str(uuid.uuid4())
    
    # Jalankan thread
    thread = threading.Thread(target=run_download_thread, args=(task_id, url, format_id, filename))
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
    return send_from_directory(DOWNLOADS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)