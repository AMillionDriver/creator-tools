# Creator Tools: Video Downloader & AI Analytics

![Creator Tools UI Screenshot]
<img width="1366" height="620" alt="image" src="https://github.com/user-attachments/assets/81b3f803-dd01-4f45-8d71-c8dc89f9f6fc" />
<img width="580" height="294" alt="image" src="https://github.com/user-attachments/assets/14d26e30-5c44-4bdb-9762-974c4ef315eb" />
<img width="573" height="637" alt="image" src="https://github.com/user-attachments/assets/65d5083d-9722-4814-b022-2cbc93e2f3a7" />
<img width="175" height="185" alt="image" src="https://github.com/user-attachments/assets/a03cce67-5cee-438a-9fd7-448ada80d0d8" />
<img width="171" height="199" alt="image" src="https://github.com/user-attachments/assets/0cd6b3a1-55f8-4557-84f3-20cdf64c93f5" />
<img width="452" height="572" alt="image" src="https://github.com/user-attachments/assets/f14e856a-d932-4cb2-8099-50b841eb1d3e" />



Aplikasi web modern yang memungkinkan pengguna untuk mengunduh video dari platform populer (seperti YouTube dan Facebook) sekaligus menyediakan wawasan analitik yang mendalam menggunakan estimasi berbasis AI. Cocok untuk kreator konten yang ingin menganalisis performa video dan audiens mereka.

## Fitur Utama

-   **Analisis Video Instan:** Dapatkan judul, thumbnail, jumlah penayangan, suka, dan komentar.
-   **Estimasi Monetisasi:** Hitung perkiraan pendapatan video (Estimasi Revenue) berdasarkan CPM dinamis yang disesuaikan dengan kategori.
-   **Estimasi Audiens AI:** Prediksi profil audiens (distribusi usia dan gender) berdasarkan kategori video, durasi, engagement, dan kata kunci judul.
-   **Progress Download Real-time:** Lacak status unduhan langsung di UI dengan progress bar yang halus.
-   **Antarmuka Pengguna Modern:** Desain Glassmorphism Dark UI yang responsif dan menarik.
-   **Dukungan Multi-format:** Pilih kualitas dan format video yang berbeda untuk diunduh.

## Teknologi yang Digunakan

### Backend (Python - Flask)
-   **Flask:** Web framework Python untuk API dan penyajian frontend.
-   **yt-dlp:** Tool canggih untuk mengunduh video dan mengekstrak metadata dari berbagai platform.
-   **python-dotenv:** Untuk mengelola variabel lingkungan dari file `.env`.
-   **threading:** Untuk menjalankan proses download di latar belakang tanpa memblokir aplikasi utama.
-   **subprocess:** Untuk menjalankan perintah eksternal seperti `yt-dlp`.

### Frontend (HTML, CSS, JavaScript)
-   **HTML5:** Struktur dasar aplikasi.
-   **CSS3 (Glassmorphism):** Styling modern dengan efek kaca buram dan animasi latar belakang yang halus.
-   **JavaScript (Vanilla JS):** Logika interaktif, komunikasi API, dan manajemen UI.
-   **Chart.js:** Library JavaScript ringan untuk membuat grafik data analitik yang interaktif.
-   **Google Fonts (Outfit):** Untuk tipografi yang modern.

## Cara Menjalankan Proyek

Pastikan Anda memiliki Node.js, Python 3.8+ dan Git terinstal di sistem Anda.

### 1. Kloning Repositori
```bash
git clone https://github.com/AMillionDriver/creator-tools.git
cd creator-tools
```

### 2. Instal Dependensi Backend
Navigasi ke direktori `backend` dan instal dependensi Python:
```bash
cd backend
pip install -r requirements.txt
cd .. # Kembali ke root project
```

### 3. Instal yt-dlp dan FFmpeg (Penting!)
`yt-dlp` memerlukan `FFmpeg` untuk penggabungan audio/video dan manipulasi lainnya. Pastikan keduanya terinstal dan dapat diakses di `PATH` sistem Anda.

-   **yt-dlp:**
    ```bash
    pip install yt-dlp
    # atau install binary-nya secara manual dari GitHub yt-dlp
    ```
-   **FFmpeg:** Instal dari [ffmpeg.org](https://ffmpeg.org/download.html) dan tambahkan ke `PATH` sistem Anda.

### 4. Instal aria2c (Opsional, tapi Direkomendasikan)
`yt-dlp` dapat menggunakan `aria2c` sebagai eksternal downloader yang lebih cepat dan mendukung resume.

-   **aria2c:** Instal dari [aria2.github.io](https://aria2.github.io/) dan tambahkan ke `PATH` sistem Anda.

### 5. Konfigurasi Lingkungan (`.env`)
Buat file `.env` di direktori `backend/` dengan konten berikut. Pastikan `ARIA2C_PATH` menunjuk ke lokasi `aria2c.exe` Anda.

```
ARIA2C_PATH="C:/Users/YourUser/Path/To/aria2c.exe" # Gunakan forward slash (/) atau double backslash (\)
FILE_EXPIRATION_TIME=3600
```
*(Catatan: Jika Anda tidak ingin menggunakan `aria2c`, hapus baris `ARIA2C_PATH` atau biarkan kosong. `yt-dlp` akan menggunakan downloader internalnya.)*

### 6. Instal Dependensi Frontend
Navigasi ke root proyek dan instal dependensi Node.js:
```bash
npm install
```

### 7. Jalankan Aplikasi
Dari root proyek, jalankan perintah development:
```bash
npm run dev
```
Ini akan menjalankan backend (Flask) dan frontend secara bersamaan.

### 8. Akses Aplikasi
Buka browser Anda dan navigasi ke `http://127.0.0.1:5000/`.

---

**_This project was assisted by Gemini CLI._**
