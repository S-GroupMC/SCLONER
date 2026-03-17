"""
Utility functions
"""
from urllib.parse import urlparse
from pathlib import Path


def extract_domain_from_url(url):
    """Extract domain from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split('/')[0]
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def normalize_url(url):
    """Normalize URL for comparison"""
    url = url.lower().strip()
    if url.startswith('http://'):
        url = url[7:]
    elif url.startswith('https://'):
        url = url[8:]
    if url.startswith('www.'):
        url = url[4:]
    url = url.rstrip('/')
    return url


def format_size(size_bytes):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def find_index_file(folder_path):
    """Find the main index.html file in a folder"""
    folder_path = Path(folder_path)
    
    # Check common locations
    candidates = [
        folder_path / 'index.html',
        folder_path / '_site' / 'index.html',
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Search recursively for any index.html
    for html_file in folder_path.rglob('index.html'):
        return html_file
    
    # Search for any .html file
    for html_file in folder_path.rglob('*.html'):
        return html_file
    
    return None
