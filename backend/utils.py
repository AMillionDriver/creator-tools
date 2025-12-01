from urllib.parse import urlparse

# Daftar domain yang diizinkan
ALLOWED_DOMAINS = {
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'tiktok.com', 'www.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com',
    'instagram.com', 'www.instagram.com',
    'soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com',
    'facebook.com', 'www.facebook.com', 'web.facebook.com', 'm.facebook.com', 'fb.watch',
    'twitter.com', 'www.twitter.com', 'mobile.twitter.com',
    'x.com', 'www.x.com'
}

def is_safe_url(url):
    """
    Memeriksa apakah URL aman dan termasuk dalam daftar domain yang diizinkan.
    Mencegah SSRF dengan menolak skema selain http/https dan domain lokal/file.
    """
    if not url:
        return False
        
    try:
        parsed_url = urlparse(url)
        
        # Hanya izinkan skema http dan https
        if parsed_url.scheme not in ('http', 'https'):
            return False
        
        domain = parsed_url.netloc.lower()
        
        # Hapus port jika ada (misal: youtube.com:80 -> youtube.com)
        if ':' in domain:
            domain = domain.split(':')[0]
            
        # Cek apakah domain ada di allow-list
        if domain in ALLOWED_DOMAINS:
            return True
            
        return False
    except Exception:
        return False
