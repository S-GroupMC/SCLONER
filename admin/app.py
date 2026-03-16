#!/usr/bin/env python3
"""
Wget Web Admin - Web interface for GNU Wget
"""

import os
import subprocess
import threading
import uuid
import json
import shutil
import signal
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wget-admin-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configuration
BASE_DIR = Path(__file__).parent.parent
WGET2_PATH = str(BASE_DIR / 'bin' / 'wget2')  # Always use local wget2
HTTRACK_PATH = str(BASE_DIR / 'bin' / 'httrack')  # Always use local httrack
PUPPETEER_SCRIPT = BASE_DIR / 'admin' / 'puppeteer-crawler.js'
DOWNLOADS_DIR = BASE_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)
PREVIEWS_DIR = BASE_DIR / 'admin' / 'static' / 'previews'
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = BASE_DIR / 'admin' / 'jobs.json'

# Store active jobs
jobs = {}


def save_jobs():
    """Save jobs to JSON file for persistence"""
    jobs_data = {}
    for job_id, job in jobs.items():
        jobs_data[job_id] = {
            'id': job.id,
            'url': job.url,
            'options': job.options,
            'use_wget2': job.use_wget2,
            'engine': job.engine,
            'status': job.status,
            'files_downloaded': job.files_downloaded,
            'total_size': job.total_size,
            'output_lines': job.output_lines[-100:],  # Last 100 lines
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'finished_at': job.finished_at.isoformat() if job.finished_at else None,
            'folder_name': job.folder_name
        }
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs_data, f, indent=2)
    except Exception as e:
        print(f"Error saving jobs: {e}")


def load_jobs():
    """Load jobs from JSON file on startup"""
    global jobs
    if not JOBS_FILE.exists():
        return
    try:
        with open(JOBS_FILE, 'r') as f:
            jobs_data = json.load(f)
        for job_id, data in jobs_data.items():
            job = WgetJob(
                data['id'],
                data['url'],
                data['options'],
                data['use_wget2'],
                data['folder_name'],
                data.get('engine', 'wget2')
            )
            job.status = data['status']
            job.files_downloaded = data['files_downloaded']
            job.total_size = data['total_size']
            job.output_lines = data['output_lines']
            if data['started_at']:
                job.started_at = datetime.fromisoformat(data['started_at'])
            if data['finished_at']:
                job.finished_at = datetime.fromisoformat(data['finished_at'])
            # Mark running jobs as stopped (server restarted)
            if job.status in ('running', 'pending', 'paused'):
                job.status = 'stopped'
                job.finished_at = datetime.now()
            jobs[job_id] = job
        print(f"Loaded {len(jobs)} jobs from file")
    except Exception as e:
        print(f"Error loading jobs: {e}")


# =============================================================================
# SITE CHANGES CHECKER - Check for updates on downloaded sites
# =============================================================================

def check_site_changes(folder_path, url):
    """
    Check if the live site has changes compared to downloaded version
    
    Args:
        folder_path: Path to the downloaded site folder
        url: Original URL of the site
    
    Returns:
        dict with changes info: {
            'has_changes': bool,
            'changed_files': list,
            'new_files': list,
            'deleted_files': list,
            'total_changes': int
        }
    """
    import hashlib
    import requests
    from bs4 import BeautifulSoup
    
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    # Файл для хранения хешей
    hashes_file = folder_path / '_wcloner' / 'file_hashes.json'
    
    try:
        # Загружаем сохранённые хеши или создаём новые
        if hashes_file.exists():
            with open(hashes_file, 'r') as f:
                saved_hashes = json.load(f)
        else:
            # Создаём хеши для текущих файлов
            saved_hashes = {}
            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and '_wcloner' not in str(file_path):
                    rel_path = str(file_path.relative_to(folder_path))
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    saved_hashes[rel_path] = file_hash
            
            # Сохраняем хеши
            hashes_file.parent.mkdir(exist_ok=True)
            with open(hashes_file, 'w') as f:
                json.dump(saved_hashes, f, indent=2)
        
        # Проверяем главную страницу онлайн
        print(f"[Changes] Checking {url}...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                'error': f'HTTP {response.status_code}',
                'has_changes': False
            }
        
        # Вычисляем хеш онлайн версии
        online_hash = hashlib.md5(response.content).hexdigest()
        
        # Находим локальный index.html
        local_index = None
        for possible_path in ['index.html', '_site/index.html', f'{urlparse(url).netloc}/index.html']:
            full_path = folder_path / possible_path
            if full_path.exists():
                local_index = full_path
                break
        
        if not local_index:
            return {
                'error': 'Local index.html not found',
                'has_changes': False
            }
        
        # Вычисляем хеш локальной версии
        with open(local_index, 'rb') as f:
            local_hash = hashlib.md5(f.read()).hexdigest()
        
        has_changes = online_hash != local_hash
        
        result = {
            'has_changes': has_changes,
            'url': url,
            'checked_at': datetime.now().isoformat(),
            'online_hash': online_hash,
            'local_hash': local_hash,
            'status': 'changes_detected' if has_changes else 'up_to_date'
        }
        
        if has_changes:
            # Пытаемся определить что изменилось
            try:
                online_soup = BeautifulSoup(response.content, 'html.parser')
                with open(local_index, 'r', encoding='utf-8') as f:
                    local_soup = BeautifulSoup(f.read(), 'html.parser')
                
                # Сравниваем title
                online_title = online_soup.title.string if online_soup.title else ''
                local_title = local_soup.title.string if local_soup.title else ''
                
                result['title_changed'] = online_title != local_title
                result['online_title'] = online_title
                result['local_title'] = local_title
                
                # Считаем количество элементов
                result['online_elements'] = len(online_soup.find_all())
                result['local_elements'] = len(local_soup.find_all())
                
            except Exception as e:
                print(f"[Changes] Error parsing HTML: {e}")
        
        print(f"[Changes] Result: {'CHANGES DETECTED' if has_changes else 'UP TO DATE'}")
        
        return result
        
    except requests.RequestException as e:
        return {
            'error': f'Network error: {str(e)}',
            'has_changes': False
        }
    except Exception as e:
        print(f"[Changes] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'has_changes': False
        }


def check_page_changes(folder_path, base_url, page_path):
    """
    Check if a specific page has changes compared to the online version.
    
    Args:
        folder_path: Path to the downloaded site folder
        base_url: Base URL of the original site
        page_path: Relative path to the HTML page (e.g. 'about.html' or 'blog/post.html')
    """
    import hashlib
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urljoin
    
    folder_path = Path(folder_path)
    local_file = folder_path / page_path
    
    if not local_file.exists():
        return {'error': f'Local file not found: {page_path}', 'has_changes': False}
    
    # Определяем онлайн URL страницы
    parsed = urlparse(base_url)
    # Если page_path содержит поддомен, строим URL из него
    parts = page_path.split(os.sep)
    if len(parts) > 1 and '.' in parts[0]:
        # Путь вида "subdomain.example.com/page.html"
        online_url = f"https://{parts[0]}/{'/'.join(parts[1:])}"
    else:
        online_url = urljoin(base_url.rstrip('/') + '/', page_path)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(online_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                'error': f'HTTP {response.status_code} for {online_url}',
                'has_changes': False
            }
        
        online_hash = hashlib.md5(response.content).hexdigest()
        online_size = len(response.content)
        
        with open(local_file, 'rb') as f:
            local_content = f.read()
            local_hash = hashlib.md5(local_content).hexdigest()
            local_size = len(local_content)
        
        has_changes = online_hash != local_hash
        
        result = {
            'has_changes': has_changes,
            'page': page_path,
            'online_url': online_url,
            'checked_at': datetime.now().isoformat(),
            'online_hash': online_hash,
            'local_hash': local_hash,
            'online_size': format_size(online_size),
            'local_size': format_size(local_size),
            'size_changed': abs(online_size - local_size) > 100,
            'status': 'changes_detected' if has_changes else 'up_to_date'
        }
        
        if has_changes:
            try:
                online_soup = BeautifulSoup(response.content, 'html.parser')
                local_soup = BeautifulSoup(local_content, 'html.parser')
                
                online_title = online_soup.title.string.strip() if online_soup.title and online_soup.title.string else ''
                local_title = local_soup.title.string.strip() if local_soup.title and local_soup.title.string else ''
                
                result['title_changed'] = online_title != local_title
                result['online_title'] = online_title
                result['local_title'] = local_title
            except Exception as e:
                print(f"[PageChanges] Error parsing HTML: {e}")
        
        print(f"[PageChanges] {page_path}: {'CHANGES' if has_changes else 'UP TO DATE'}")
        return result
        
    except requests.RequestException as e:
        return {
            'error': f'Network error: {str(e)}',
            'has_changes': False
        }
    except Exception as e:
        print(f"[PageChanges] Error: {e}")
        return {
            'error': str(e),
            'has_changes': False
        }


def check_all_pages_changes(folder_path, base_url, max_pages=50):
    """
    Check all HTML pages in a folder for changes.
    Returns detailed info for each page.
    """
    import hashlib
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urljoin
    
    folder_path = Path(folder_path)
    results = []
    
    # Find all HTML files
    html_files = list(folder_path.rglob('*.html'))[:max_pages]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    for html_file in html_files:
        page_path = str(html_file.relative_to(folder_path))
        
        # Determine online URL
        parts = page_path.split(os.sep)
        if len(parts) > 1 and '.' in parts[0]:
            online_url = f"https://{parts[0]}/{'/'.join(parts[1:])}"
        else:
            online_url = urljoin(base_url.rstrip('/') + '/', page_path)
        
        result = {
            'page': page_path,
            'name': html_file.name,
            'online_url': online_url,
            'local_size': format_size(html_file.stat().st_size),
            'local_size_bytes': html_file.stat().st_size
        }
        
        try:
            response = requests.get(online_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                result['status'] = 'error'
                result['error'] = f'HTTP {response.status_code}'
                result['has_changes'] = False
            else:
                online_hash = hashlib.md5(response.content).hexdigest()
                online_size = len(response.content)
                
                with open(html_file, 'rb') as f:
                    local_content = f.read()
                    local_hash = hashlib.md5(local_content).hexdigest()
                
                has_changes = online_hash != local_hash
                result['has_changes'] = has_changes
                result['online_size'] = format_size(online_size)
                result['online_size_bytes'] = online_size
                result['size_diff'] = online_size - html_file.stat().st_size
                result['status'] = 'changed' if has_changes else 'unchanged'
                
                if has_changes:
                    try:
                        online_soup = BeautifulSoup(response.content, 'html.parser')
                        local_soup = BeautifulSoup(local_content, 'html.parser')
                        
                        online_title = online_soup.title.string.strip() if online_soup.title and online_soup.title.string else ''
                        local_title = local_soup.title.string.strip() if local_soup.title and local_soup.title.string else ''
                        
                        result['title_changed'] = online_title != local_title
                        result['online_title'] = online_title
                        result['local_title'] = local_title
                        
                        # Count elements difference
                        result['online_elements'] = len(online_soup.find_all())
                        result['local_elements'] = len(local_soup.find_all())
                    except:
                        pass
                        
        except requests.RequestException as e:
            result['status'] = 'error'
            result['error'] = str(e)[:50]
            result['has_changes'] = False
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)[:50]
            result['has_changes'] = False
        
        results.append(result)
    
    # Summary
    changed = sum(1 for r in results if r.get('has_changes'))
    unchanged = sum(1 for r in results if r.get('status') == 'unchanged')
    errors = sum(1 for r in results if r.get('status') == 'error')
    
    return {
        'total': len(results),
        'changed': changed,
        'unchanged': unchanged,
        'errors': errors,
        'pages': results,
        'checked_at': datetime.now().isoformat()
    }


# =============================================================================
# INTEGRITY CHECK - Verify all referenced resources are downloaded
# =============================================================================

def check_site_integrity(folder_path):
    """
    Parse HTML and CSS files to find all referenced resources,
    then check if each resource exists locally.
    
    Returns dict with missing files list and stats.
    """
    import re
    from urllib.parse import urlparse, unquote
    
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    referenced = {}  # path -> set of referencing files
    existing_files = set()
    
    # Collect all existing files
    for f in folder_path.rglob('*'):
        if f.is_file() and '_wcloner' not in str(f):
            rel = str(f.relative_to(folder_path))
            existing_files.add(rel)
    
    def normalize_ref(ref_path, context_file):
        """Resolve a relative reference from a context file to a folder-relative path"""
        ref_path = ref_path.strip().strip("'\"")
        ref_path = unquote(ref_path)
        
        # Skip data URIs, external URLs, anchors, empty
        if not ref_path or ref_path.startswith(('data:', 'http://', 'https://', 'mailto:', 'tel:', '#', 'javascript:', '//')):
            return None
        
        # Remove query string and fragment
        ref_path = ref_path.split('?')[0].split('#')[0]
        if not ref_path:
            return None
        
        # Resolve relative to the directory of context_file
        context_dir = str(Path(context_file).parent)
        if ref_path.startswith('/'):
            # Absolute path from site root - find the subdomain/domain dir
            parts = context_file.split('/')
            # If inside a subdomain dir like "sub.example.com/page.html"
            if len(parts) > 1 and '.' in parts[0]:
                resolved = parts[0] + ref_path
            else:
                resolved = ref_path.lstrip('/')
        else:
            if context_dir and context_dir != '.':
                resolved = str(Path(context_dir) / ref_path)
            else:
                resolved = ref_path
        
        # Normalize path (resolve ..)
        try:
            resolved = str(Path(resolved))
            # Remove leading ./
            if resolved.startswith('./'):
                resolved = resolved[2:]
        except:
            return None
        
        return resolved
    
    # Parse HTML files
    html_tag_re = re.compile(r'(?:src|href|data-src|poster|srcset)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    css_url_re = re.compile(r'url\(\s*["\']?([^"\')\s]+)["\']?\s*\)', re.IGNORECASE)
    css_import_re = re.compile(r'@import\s+["\']([^"\']+)["\']', re.IGNORECASE)
    js_import_re = re.compile(r'(?:import|from)\s+["\']([^"\']+)["\']', re.IGNORECASE)
    
    for f in folder_path.rglob('*'):
        if not f.is_file() or '_wcloner' in str(f):
            continue
        
        rel_path = str(f.relative_to(folder_path))
        ext = f.suffix.lower()
        
        try:
            if ext in ('.html', '.htm'):
                content = f.read_text(encoding='utf-8', errors='ignore')
                # HTML tags: src, href, data-src, poster
                for match in html_tag_re.finditer(content):
                    ref = match.group(1)
                    # Handle srcset (multiple URLs)
                    if ',' in ref and ' ' in ref:
                        for part in ref.split(','):
                            url_part = part.strip().split(' ')[0]
                            resolved = normalize_ref(url_part, rel_path)
                            if resolved:
                                referenced.setdefault(resolved, set()).add(rel_path)
                    else:
                        resolved = normalize_ref(ref, rel_path)
                        if resolved:
                            referenced.setdefault(resolved, set()).add(rel_path)
                
                # Inline CSS url()
                for match in css_url_re.finditer(content):
                    resolved = normalize_ref(match.group(1), rel_path)
                    if resolved:
                        referenced.setdefault(resolved, set()).add(rel_path)
                
            elif ext == '.css':
                content = f.read_text(encoding='utf-8', errors='ignore')
                # CSS url()
                for match in css_url_re.finditer(content):
                    resolved = normalize_ref(match.group(1), rel_path)
                    if resolved:
                        referenced.setdefault(resolved, set()).add(rel_path)
                # @import
                for match in css_import_re.finditer(content):
                    resolved = normalize_ref(match.group(1), rel_path)
                    if resolved:
                        referenced.setdefault(resolved, set()).add(rel_path)
                
            elif ext in ('.js', '.mjs'):
                content = f.read_text(encoding='utf-8', errors='ignore')
                # JS import/from (static imports and chunk references)
                for match in js_import_re.finditer(content):
                    ref = match.group(1)
                    if ref.endswith(('.js', '.mjs', '.css', '.json')):
                        resolved = normalize_ref(ref, rel_path)
                        if resolved:
                            referenced.setdefault(resolved, set()).add(rel_path)
                # Dynamic import() 
                dynamic_re = re.compile(r'import\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
                for match in dynamic_re.finditer(content):
                    resolved = normalize_ref(match.group(1), rel_path)
                    if resolved:
                        referenced.setdefault(resolved, set()).add(rel_path)
        except Exception as e:
            print(f"[Integrity] Error parsing {rel_path}: {e}")
            continue
    
    # Find missing files
    missing = []
    for ref_path, sources in referenced.items():
        if ref_path not in existing_files:
            # Try with index.html appended for directory refs
            if ref_path + '/index.html' not in existing_files and ref_path.rstrip('/') + '/index.html' not in existing_files:
                missing.append({
                    'path': ref_path,
                    'referenced_by': sorted(list(sources))[:5],
                    'ref_count': len(sources)
                })
    
    # Categorize missing by type
    missing_by_type = {'css': 0, 'js': 0, 'images': 0, 'fonts': 0, 'other': 0}
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp', '.avif'}
    font_exts = {'.woff', '.woff2', '.ttf', '.eot', '.otf'}
    
    for item in missing:
        ext = Path(item['path']).suffix.lower()
        if ext in ('.css',):
            missing_by_type['css'] += 1
        elif ext in ('.js', '.mjs'):
            missing_by_type['js'] += 1
        elif ext in image_exts:
            missing_by_type['images'] += 1
        elif ext in font_exts:
            missing_by_type['fonts'] += 1
        else:
            missing_by_type['other'] += 1
    
    # Sort: most referenced first
    missing.sort(key=lambda x: x['ref_count'], reverse=True)
    
    return {
        'total_referenced': len(referenced),
        'total_existing': len(existing_files),
        'total_missing': len(missing),
        'missing_by_type': missing_by_type,
        'missing': missing[:200],  # Limit to 200
        'is_complete': len(missing) == 0,
        'checked_at': datetime.now().isoformat()
    }


def download_missing_files(folder_path, base_url, missing_paths):
    """
    Download missing files from the original site.
    Returns results for each file.
    """
    import requests
    from urllib.parse import urlparse
    
    folder_path = Path(folder_path)
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    for file_path in missing_paths:
        # Determine URL
        parts = file_path.split('/')
        if len(parts) > 1 and '.' in parts[0]:
            # Subdomain path like "sub.example.com/assets/style.css"
            url = f"https://{parts[0]}/{'/'.join(parts[1:])}"
        else:
            parsed = urlparse(base_url)
            url = f"{parsed.scheme}://{parsed.netloc}/{file_path}"
        
        local_file = folder_path / file_path
        
        try:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if response.status_code == 200 and len(response.content) > 0:
                local_file.parent.mkdir(parents=True, exist_ok=True)
                with open(local_file, 'wb') as f:
                    f.write(response.content)
                
                results.append({
                    'path': file_path,
                    'status': 'downloaded',
                    'size': format_size(len(response.content)),
                    'url': url
                })
                print(f"[Download] OK: {file_path} ({format_size(len(response.content))})")
            else:
                results.append({
                    'path': file_path,
                    'status': 'failed',
                    'error': f'HTTP {response.status_code}',
                    'url': url
                })
                print(f"[Download] FAIL: {file_path} - HTTP {response.status_code}")
        except Exception as e:
            results.append({
                'path': file_path,
                'status': 'error',
                'error': str(e),
                'url': url
            })
            print(f"[Download] ERROR: {file_path} - {e}")
    
    downloaded = sum(1 for r in results if r['status'] == 'downloaded')
    failed = sum(1 for r in results if r['status'] != 'downloaded')
    
    return {
        'total': len(results),
        'downloaded': downloaded,
        'failed': failed,
        'results': results
    }


# =============================================================================
# PREVIEW SCREENSHOT GENERATOR - Create preview image of downloaded site
# =============================================================================

def generate_preview_screenshot(folder_path, main_domain, job_id, index_file=None):
    """
    Generate preview screenshot of the main page using Puppeteer
    
    Args:
        folder_path: Path to the downloaded site folder
        main_domain: Main domain name (e.g., example.com)
        job_id: Job ID for unique filename
        index_file: Optional path to index.html (if already found)
    
    Returns:
        Path to generated preview image or None
    """
    folder_path = Path(folder_path)
    
    # Use provided index_file or search for it
    if not index_file:
        # Find index.html in folder or _site/
        index_paths = [
            folder_path / 'index.html',
            folder_path / '_site' / 'index.html',
            folder_path / main_domain / 'index.html'
        ]
        
        for path in index_paths:
            if path.exists():
                index_file = path
                break
        
        # If still not found, use find_index_file
        if not index_file:
            index_file = find_index_file(folder_path)
    
    if not index_file:
        print(f"[Preview] index.html not found in {folder_path}")
        return None
    
    try:
        # Create preview filename
        preview_filename = f"{main_domain.replace('.', '_')}_{job_id}.png"
        preview_path = PREVIEWS_DIR / preview_filename
        
        # Also save in site folder
        site_preview_path = folder_path / 'preview.png'
        
        # Use Python's Playwright instead of Puppeteer (more reliable)
        # First try simple approach with subprocess and chromium
        import shutil
        
        # Check if we have chromium/chrome
        chrome_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            shutil.which('chromium'),
            shutil.which('google-chrome')
        ]
        
        chrome_path = None
        for p in chrome_paths:
            if p and Path(p).exists():
                chrome_path = p
                break
        
        if chrome_path:
            # Use Chrome headless to screenshot the LIVE site (not local file)
            site_url = f'https://{main_domain}'
            
            result = subprocess.run([
                chrome_path,
                '--headless=new',
                '--disable-gpu',
                '--no-sandbox',
                f'--screenshot={preview_path}',
                '--window-size=1280,800',
                site_url
            ], capture_output=True, text=True, timeout=30)
            
            if preview_path.exists():
                # Copy to site folder
                import shutil as sh
                sh.copy(preview_path, site_preview_path)
                print(f"[Preview] Screenshot created with Chrome: {preview_filename}")
                return preview_path
        
        # Fallback: create simple placeholder image
        print(f"[Preview] Chrome not available, creating placeholder")
        # Create a simple 1x1 pixel PNG as placeholder
        placeholder_png = b'\\x89PNG\\r\\n\\x1a\\n\\x00\\x00\\x00\\rIHDR\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x01\\x08\\x02\\x00\\x00\\x00\\x90wS\\xde\\x00\\x00\\x00\\x0cIDATx\\x9cc\\xf8\\x0f\\x00\\x00\\x01\\x01\\x00\\x05\\x18\\xd8N\\x00\\x00\\x00\\x00IEND\\xaeB`\\x82'
        preview_path.write_bytes(placeholder_png)
        site_preview_path.write_bytes(placeholder_png)
        return preview_path
            
    except Exception as e:
        print(f"[Preview] ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


# =============================================================================
# SERVER FILES GENERATOR - Create standalone server for each downloaded site
# =============================================================================

def generate_vue_wrapper(folder_path, main_domain, port=3000, backend_port=3001):
    """
    Generate Vue wrapper with iframe for a downloaded site
    
    Args:
        folder_path: Path to the downloaded site folder
        main_domain: Main domain name (e.g., example.com)
        port: Port for Vite dev server (default: 3000)
        backend_port: Port for backend server serving static files (default: 3001)
    """
    folder_path = Path(folder_path)
    if not folder_path.exists():
        print(f"[Vue Generator] Folder not found: {folder_path}")
        return False
    
    template_dir = Path(__file__).parent / 'templates' / 'vue_wrapper'
    if not template_dir.exists():
        print(f"[Vue Generator] Vue wrapper templates not found")
        return False
    
    try:
        # Create vue-app directory
        vue_dir = folder_path / 'vue-app'
        vue_dir.mkdir(exist_ok=True)
        
        # Create src directory
        src_dir = vue_dir / 'src'
        src_dir.mkdir(exist_ok=True)
        
        # Move original files to _site
        site_dir = folder_path / '_site'
        if not site_dir.exists():
            site_dir.mkdir(exist_ok=True)
            # Move all files except vue-app and _site to _site
            for item in folder_path.iterdir():
                if item.name not in ['vue-app', '_site', '_wcloner', 'server.js', 'package.json', 'README.md']:
                    target = site_dir / item.name
                    if not target.exists():
                        shutil.move(str(item), str(target))
        
        package_name = main_domain.replace('.', '-')
        
        # Copy and process templates
        replacements = {
            '{{MAIN_DOMAIN}}': main_domain,
            '{{PACKAGE_NAME}}': package_name,
            '{{PORT}}': str(port),
            '{{BACKEND_PORT}}': str(backend_port)
        }
        
        # index.html
        with open(template_dir / 'index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        for key, val in replacements.items():
            content = content.replace(key, val)
        with open(vue_dir / 'index.html', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # App.vue
        shutil.copy(template_dir / 'App.vue', src_dir / 'App.vue')
        
        # main.js
        shutil.copy(template_dir / 'main.js', src_dir / 'main.js')
        
        # package.json
        with open(template_dir / 'package.json', 'r', encoding='utf-8') as f:
            content = f.read()
        for key, val in replacements.items():
            content = content.replace(key, val)
        with open(vue_dir / 'package.json', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # vite.config.js
        with open(template_dir / 'vite.config.js', 'r', encoding='utf-8') as f:
            content = f.read()
        for key, val in replacements.items():
            content = content.replace(key, val)
        with open(vue_dir / 'vite.config.js', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Backend server.js
        with open(template_dir / 'server.js', 'r', encoding='utf-8') as f:
            content = f.read()
        for key, val in replacements.items():
            content = content.replace(key, val)
        backend_server = folder_path / 'backend-server.js'
        with open(backend_server, 'w', encoding='utf-8') as f:
            f.write(content)
        os.chmod(backend_server, 0o755)
        
        # Create README
        readme_content = f"""# {main_domain} - Vue Wrapper

Этот сайт был скачан с помощью WCLoner и обёрнут в Vue.js приложение.

## Структура

```
{folder_path.name}/
├── vue-app/           ← Vue приложение (обёртка)
│   ├── src/
│   │   ├── App.vue
│   │   └── main.js
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── _site/             ← Скачанный контент
│   ├── index.html
│   ├── css/
│   └── js/
└── backend-server.js  ← Сервер для статики
```

## Быстрый старт

### 1. Установка зависимостей

```bash
cd vue-app
npm install
```

### 2. Запуск

Откройте **два терминала**:

**Терминал 1** - Backend сервер (статика):
```bash
node backend-server.js
```

**Терминал 2** - Vue dev сервер:
```bash
cd vue-app
npm run dev
```

Откройте: http://localhost:{port}

## Возможности

- ✅ Vue.js обёртка с iframe
- ✅ SEO оптимизация (meta tags, structured data)
- ✅ Синхронизация URL между iframe и родителем
- ✅ Извлечение контента для поисковиков
- ✅ Hot Module Replacement (HMR)
- ✅ Готово к продакшену (npm run build)

## Production Build

```bash
cd vue-app
npm run build
```

Результат в `vue-app/dist/`

---
Создано WCLoner
"""
        
        readme_file = folder_path / 'README-VUE.md'
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"[Vue Generator] ✅ Generated Vue wrapper for {main_domain}")
        print(f"  - vue-app/index.html")
        print(f"  - vue-app/src/App.vue")
        print(f"  - vue-app/src/main.js")
        print(f"  - vue-app/package.json")
        print(f"  - vue-app/vite.config.js")
        print(f"  - backend-server.js")
        print(f"  - README-VUE.md")
        print(f"  - Moved content to _site/")
        
        return True
        
    except Exception as e:
        print(f"[Vue Generator] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_server_files(folder_path, main_domain, port=3000, with_vue=False):
    """
    Generate server.js, platform-integration.js, and package.json for a downloaded site
    
    Args:
        folder_path: Path to the downloaded site folder (e.g., /downloads/example.com)
        main_domain: Main domain name (e.g., example.com)
        port: Port number for the server (default: 3000)
        with_vue: Generate Vue wrapper instead of simple server (default: False)
    """
    if with_vue:
        return generate_vue_wrapper(folder_path, main_domain, port, port + 1)
    folder_path = Path(folder_path)
    if not folder_path.exists():
        print(f"[Server Generator] Folder not found: {folder_path}")
        return False
    
    # Extract domain info
    local_domain = main_domain.replace('.com', '.local').replace('.net', '.local').replace('.org', '.local')
    
    # Find all subdomains in the folder
    subdomains = []
    try:
        for item in folder_path.parent.iterdir():
            if item.is_dir() and '.' in item.name and main_domain in item.name:
                subdomains.append(item.name)
    except Exception as e:
        print(f"[Server Generator] Error scanning subdomains: {e}")
    
    # Read templates
    template_dir = Path(__file__).parent / 'templates'
    server_template_path = template_dir / 'server_template.js'
    platform_template_path = template_dir / 'platform_integration_template.js'
    
    if not server_template_path.exists() or not platform_template_path.exists():
        print(f"[Server Generator] Templates not found in {template_dir}")
        return False
    
    try:
        # Read server template
        with open(server_template_path, 'r', encoding='utf-8') as f:
            server_content = f.read()
        
        # Replace placeholders in server.js
        server_content = server_content.replace('{{PORT}}', str(port))
        server_content = server_content.replace('{{MAIN_DOMAIN}}', main_domain)
        server_content = server_content.replace('{{LOCAL_DOMAIN}}', local_domain)
        server_content = server_content.replace('{{SUBDOMAINS_JSON}}', json.dumps(subdomains))
        
        # Read platform integration template
        with open(platform_template_path, 'r', encoding='utf-8') as f:
            platform_content = f.read()
        
        # Replace placeholders in platform-integration.js
        platform_content = platform_content.replace('{{MAIN_DOMAIN}}', main_domain)
        platform_content = platform_content.replace('{{LOCAL_DOMAIN}}', local_domain)
        platform_content = platform_content.replace('{{SUBDOMAINS_JSON}}', json.dumps(subdomains))
        
        # Create _wcloner directory
        wcloner_dir = folder_path / '_wcloner'
        wcloner_dir.mkdir(exist_ok=True)
        
        # Write server.js to main folder
        server_file = folder_path / 'server.js'
        with open(server_file, 'w', encoding='utf-8') as f:
            f.write(server_content)
        os.chmod(server_file, 0o755)  # Make executable
        
        # Write platform-integration.js to _wcloner
        platform_file = wcloner_dir / 'platform-integration.js'
        with open(platform_file, 'w', encoding='utf-8') as f:
            f.write(platform_content)
        
        # Create package.json
        package_json = {
            "name": main_domain.replace('.', '-'),
            "version": "1.0.0",
            "description": f"WCLoner standalone server for {main_domain}",
            "main": "server.js",
            "scripts": {
                "start": "node server.js",
                "dev": f"PORT={port} node server.js"
            },
            "keywords": ["wcloner", "static-server"],
            "author": "WCLoner",
            "license": "MIT"
        }
        
        package_file = folder_path / 'package.json'
        with open(package_file, 'w', encoding='utf-8') as f:
            json.dump(package_json, f, indent=2)
        
        # Create README.md
        readme_content = f"""# {main_domain} - WCLoner Standalone Server

Этот сайт был скачан с помощью WCLoner и готов к запуску.

## Быстрый старт

```bash
# Запустить сервер
node server.js

# Или с npm
npm start
```

Сервер запустится на порту {port}.

## Доступ к сайту

- Главный домен: http://localhost:{port}
- Локальный домен: http://{local_domain}:{port}

## Поддомены

{chr(10).join(f'- http://{sub.replace(main_domain, local_domain)}:{port}' for sub in subdomains[:5])}
{f'... и ещё {len(subdomains) - 5} поддоменов' if len(subdomains) > 5 else ''}

## Настройка hosts (опционально)

Добавьте в `/etc/hosts` (macOS/Linux) или `C:\\Windows\\System32\\drivers\\etc\\hosts` (Windows):

```
127.0.0.1 {local_domain}
{chr(10).join(f'127.0.0.1 {sub.replace(main_domain, local_domain)}' for sub in subdomains[:10])}
```

## Возможности

- ✅ Автоматическая маршрутизация по поддоменам
- ✅ Переписывание URL в HTML
- ✅ Клиентская навигация между страницами
- ✅ Блокировка внешних трекеров
- ✅ Gzip сжатие
- ✅ CORS поддержка

---
Создано WCLoner
"""
        
        readme_file = folder_path / 'README.md'
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"[Server Generator] ✅ Generated server files for {main_domain}")
        print(f"  - server.js")
        print(f"  - _wcloner/platform-integration.js")
        print(f"  - package.json")
        print(f"  - README.md")
        print(f"  - Found {len(subdomains)} subdomains")
        
        return True
        
    except Exception as e:
        print(f"[Server Generator] ❌ Error generating files: {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# DOMAIN FILTERING - Common logic for all engines (wget2, httrack, smart)
# =============================================================================

# Blocked external domains and patterns
BLOCKED_DOMAINS = [
    # Social media
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
    'tiktok.com', 'linkedin.com', 'pinterest.com', 'snapchat.com',
    'x.com', 'threads.net',
    # Tracking & Analytics
    'google-analytics.com', 'googletagmanager.com', 'doubleclick.net',
    'googlesyndication.com', 'googleadservices.com',
    'facebook.net', 'fbcdn.net',
    'hotjar.com', 'mixpanel.com', 'segment.com', 'amplitude.com',
    'newrelic.com', 'nr-data.net', 'sentry.io',
    # Advertising
    'adsrvr.org', 'adroll.com', 'criteo.com', 'taboola.com', 'outbrain.com',
    # Ticket/Event platforms (external)
    'ticketmaster.com', 'ticketmaster.net', 'livenation.com',
    'axs.com', 'eventbrite.com', 'stubhub.com',
    'seatgeek.com', 'vividseats.com',
    # Chat/Support widgets
    'intercom.io', 'zendesk.com', 'drift.com', 'crisp.chat',
    'tawk.to', 'livechat.com', 'olark.com',
    'gorgias.io', 'gorgias.help',
    # Marketing platforms
    'mailchimp.com', 'klaviyo.com', 'hubspot.com', 'marketo.com',
    'pardot.com', 'salesforce.com',
    'attentivemobile.com', 'attn.tv',
    'hive.co', 'privy.com',
    # Other external services
    '9gtb.com', 'trustedsite.com', 'trustpilot.com',
    'yotpo.com', 'stamped.io', 'loox.io',
    'rechargeapps.com', 'recurly.com',
]

# Allowed CDN patterns (resources needed for page display)
ALLOWED_CDN_PATTERNS = [
    'cdn.shopify.com', 'fonts.shopifycdn.com',
    'cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com',
    'fonts.googleapis.com', 'fonts.gstatic.com',
    'use.typekit.net', 'use.fontawesome.com',
]


def get_domain_filter_config(job):
    """
    Build domain filtering configuration for any engine.
    Returns dict with allowed_domains, blocked_patterns, etc.
    """
    opts = job.options
    parsed = urlparse(job.url)
    main_domain = parsed.netloc
    
    if main_domain.startswith('www.'):
        base_domain = main_domain[4:]
    else:
        base_domain = main_domain
    
    # Build allowed domains list
    allowed_domains = set()
    allowed_domains.add(base_domain)
    allowed_domains.add(f'www.{base_domain}')
    allowed_domains.add(main_domain)
    
    # Include subdomains
    if opts.get('include_subdomains', False):
        allowed_domains.add(f'*.{base_domain}')
    
    # Extra domains from user selection
    extra_domains = opts.get('extra_domains', '')
    if extra_domains:
        for d in extra_domains.split(','):
            d = d.strip()
            if d:
                allowed_domains.add(d)
    
    # Add allowed CDN patterns
    allowed_cdn = set(ALLOWED_CDN_PATTERNS)
    
    return {
        'base_domain': base_domain,
        'main_domain': main_domain,
        'allowed_domains': allowed_domains,
        'allowed_cdn': allowed_cdn,
        'blocked_domains': BLOCKED_DOMAINS,
    }


def is_domain_allowed(domain, filter_config):
    """Check if a domain is allowed based on filter config"""
    # Check blocked list first
    for blocked in filter_config['blocked_domains']:
        if blocked in domain:
            return False
    
    # Check if it's the main domain or subdomain
    base = filter_config['base_domain']
    if domain == base or domain.endswith(f'.{base}'):
        return True
    
    # Check allowed domains
    for allowed in filter_config['allowed_domains']:
        if allowed.startswith('*.'):
            pattern = allowed[2:]
            if domain == pattern or domain.endswith(f'.{pattern}'):
                return True
        elif domain == allowed:
            return True
    
    # Check allowed CDN
    for cdn in filter_config['allowed_cdn']:
        if domain == cdn or domain.endswith(f'.{cdn}'):
            return True
    
    return False


class WgetJob:
    def __init__(self, job_id, url, options, use_wget2=False, folder_name=None, engine='wget2'):
        self.id = job_id
        self.url = url
        self.options = options
        self.use_wget2 = use_wget2
        self.engine = engine  # 'wget', 'wget2', 'puppeteer', 'httrack', 'smart'
        self.status = 'pending'
        self.progress = 0
        self.files_downloaded = 0
        self.total_size = '0 B'
        self.output_lines = []
        self.process = None
        self.started_at = None
        self.finished_at = None
        self.stop_requested = False  # Flag to stop Smart mode loop
        self.preview_image = None  # Path to preview screenshot
        # Use folder_name if provided, otherwise fall back to job_id
        self.folder_name = folder_name or job_id
        self.output_dir = DOWNLOADS_DIR / self.folder_name
        self.output_dir.mkdir(exist_ok=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'url': self.url,
            'options': self.options,
            'status': self.status,
            'progress': self.progress,
            'files_downloaded': self.files_downloaded,
            'total_size': self.total_size,
            'output_lines': self.output_lines[-50:],  # Last 50 lines
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'output_dir': str(self.output_dir),
            'use_wget2': self.use_wget2,
            'engine': self.engine,
            'preview_image': self.preview_image
        }


def build_wget_command(job):
    """Build wget command from job options - always uses wget2"""
    print(f"[DEBUG] Building command for job {job.id}")
    print(f"[DEBUG] Options: {job.options}")
    print(f"[DEBUG] include_subdomains: {job.options.get('include_subdomains')}")
    print(f"[DEBUG] extra_domains: {job.options.get('extra_domains')}")
    
    # Always use wget2 (faster, HTTP/2 support)
    cmd = [WGET2_PATH]
    # wget2-specific optimizations (all verified options)
    cmd.append('--http2')  # Enable HTTP/2
    cmd.append('--compression=br,gzip,zstd')  # All compression types
    cmd.append('--tcp-fastopen')  # TCP Fast Open
    cmd.append('--dns-cache')  # DNS caching
    cmd.append('--hsts')  # HTTP Strict Transport Security
    
    # Progress bar style
    if job.options.get('progress_bar', True):
        cmd.append('--progress=bar')
    
    # Metalink support for mirrors
    if job.options.get('metalink', False):
        cmd.append('--metalink')
    
    # Parallel threads (default 5, max 20)
    threads = job.options.get('parallel_threads', 10)
    cmd.extend(['--max-threads', str(threads)])
    
    # HTTP/2 request window for parallel requests
    http2_window = job.options.get('http2_window', 30)
    cmd.extend(['--http2-request-window', str(http2_window)])
    
    # Chunk size for parallel download of single files
    chunk_size = job.options.get('chunk_size', '')
    if chunk_size:
        cmd.extend(['--chunk-size', chunk_size])
    opts = job.options
    
    # Recursive options
    if opts.get('recursive', False):
        cmd.append('-r')
        depth = opts.get('depth', 2)
        cmd.extend(['-l', str(depth)])
    
    # Page requisites (CSS, JS, images)
    # -p downloads resources needed for page display
    if opts.get('page_requisites', True):
        cmd.append('-p')
    
    # Convert links for offline viewing
    if opts.get('convert_links', True):
        cmd.append('-k')
    
    # Adjust extensions (.html)
    if opts.get('adjust_extensions', True):
        cmd.append('-E')
    
    # =========================================================================
    # DOMAIN FILTERING - Using common filter config
    # =========================================================================
    filter_config = get_domain_filter_config(job)
    base_domain = filter_config['base_domain']
    
    # Build domains list for -D option
    domains_list = [base_domain, f'www.{base_domain}']
    
    # Include subdomains
    if opts.get('include_subdomains', False):
        domains_list.append(f'.{base_domain}')
    
    # Add allowed domains (extra domains from user)
    for domain in filter_config['allowed_domains']:
        if domain not in domains_list and not domain.startswith('*.'):
            domains_list.append(domain)
    
    # Add allowed CDN for resources
    for cdn in filter_config['allowed_cdn']:
        if cdn not in domains_list:
            domains_list.append(cdn)
    
    # Domain filtering
    cmd.extend(['-D', ','.join(domains_list)])
    
    # Reject patterns for blocked domains
    reject_domains = ','.join([f'*{d}*' for d in filter_config['blocked_domains'][:20]])  # Limit to avoid too long command
    cmd.extend(['--reject-regex', reject_domains])
    
    # Span hosts - allow following links to subdomains/extra domains
    cmd.append('-H')
    
    # No parent (don't go up directories)
    if opts.get('no_parent', True):
        cmd.append('--no-parent')
    
    # Rate limit
    rate_limit = opts.get('rate_limit', '')
    if rate_limit:
        cmd.extend(['--limit-rate', rate_limit])
    
    # Wait between requests
    wait = opts.get('wait', 0.5)
    if wait:
        cmd.extend(['--wait', str(wait)])
    
    # Random wait
    if opts.get('random_wait', False):
        cmd.append('--random-wait')
    
    # User agent
    user_agent = opts.get('user_agent', '')
    if user_agent:
        cmd.extend(['--user-agent', user_agent])
    
    # Reject patterns
    reject = opts.get('reject', '')
    if reject:
        cmd.extend(['--reject', reject])
    
    # Accept patterns
    accept = opts.get('accept', '')
    if accept:
        cmd.extend(['--accept', accept])
    
    # Timeout
    timeout = opts.get('timeout', 30)
    cmd.extend(['--timeout', str(timeout)])
    
    # Retries
    retries = opts.get('retries', 3)
    cmd.extend(['--tries', str(retries)])
    
    # Restrict file names (fix query strings in filenames)
    if opts.get('restrict_file_names', True):
        cmd.append('--restrict-file-names=windows')
    
    # Trust server names (use final URL after redirects)
    if opts.get('trust_server_names', True):
        cmd.append('--trust-server-names')
    
    # Ignore robots.txt
    if opts.get('ignore_robots', False):
        if job.use_wget2:
            cmd.append('--robots=off')
        else:
            cmd.append('-e')
            cmd.append('robots=off')
    
    # No cookies (each page as new visit)
    if opts.get('no_cookies', False):
        cmd.append('--no-cookies')
    
    # Mirror mode (recursive + timestamps + infinite depth)
    if opts.get('mirror_mode', False):
        cmd.append('--mirror')
    
    # Continue/resume download (timestamping + no-clobber)
    if opts.get('continue_download', False):
        cmd.append('--timestamping')
        cmd.append('--no-clobber')
    
    # Always add no-clobber to prevent re-downloading existing files
    if not opts.get('continue_download', False) and not opts.get('mirror_mode', False):
        cmd.append('--no-clobber')
    
    # Output directory
    cmd.extend(['-P', str(job.output_dir)])
    
    # Progress output
    cmd.append('--progress=dot:default')
    
    # URL
    cmd.append(job.url)
    
    print(f"[DEBUG] Final wget command: {' '.join(cmd)}")
    return cmd


def build_httrack_command(job):
    """Build httrack command from job options using common domain filtering"""
    cmd = [HTTRACK_PATH]
    opts = job.options
    
    # Get common filter config
    filter_config = get_domain_filter_config(job)
    base_domain = filter_config['base_domain']
    
    # URL first
    cmd.append(job.url)
    
    # Output directory
    cmd.extend(['-O', str(job.output_dir)])
    
    # Depth
    depth = opts.get('depth', 2)
    cmd.extend(['-r' + str(depth)])
    
    # IMPORTANT: Preserve original file extensions (don't convert to .html)
    cmd.append('-%e0')
    
    # Near mode - get external files needed for page display
    cmd.append('--near')
    
    # Disable robots.txt
    cmd.append('--robots=0')
    
    # Keep connections alive
    cmd.append('--keep-alive')
    
    # =========================================================================
    # DOMAIN FILTERING - Using common filter config
    # =========================================================================
    
    # Allow main domain and subdomains
    if opts.get('include_subdomains', False):
        cmd.append(f'+*.{base_domain}/*')
        cmd.append(f'+{base_domain}/*')
        cmd.append(f'+www.{base_domain}/*')
    else:
        cmd.append(f'+{filter_config["main_domain"]}/*')
    
    # Add extra domains from user selection
    for domain in filter_config['allowed_domains']:
        if not domain.startswith('*.') and domain != base_domain and domain != f'www.{base_domain}':
            cmd.append(f'+{domain}/*')
    
    # Add allowed CDN patterns
    for cdn in filter_config['allowed_cdn']:
        cmd.append(f'+{cdn}/*')
    
    # =========================================================================
    # BLOCK ALL EXTERNAL DOMAINS - Critical for clean downloads
    # =========================================================================
    
    # Block all domains from BLOCKED_DOMAINS list
    for blocked in filter_config['blocked_domains']:
        cmd.append(f'-*{blocked}*')
    
    # Block everything else by default (must be last)
    cmd.append('-*')
    
    # User agent
    user_agent = opts.get('user_agent', '')
    if user_agent:
        cmd.extend(['-F', user_agent])
    
    # Timeout
    timeout = opts.get('timeout', 30)
    cmd.extend(['-T', str(timeout)])
    
    # Retries
    retries = opts.get('retries', 3)
    cmd.extend(['-R', str(retries)])
    
    # Continue download
    if opts.get('continue_download', False):
        cmd.append('--continue')
    
    # Verbose output
    cmd.append('-v')
    
    return cmd


def build_puppeteer_command(job):
    """Build puppeteer crawler command from job options"""
    cmd = ['node', str(PUPPETEER_SCRIPT)]
    opts = job.options
    
    # URL
    cmd.append(job.url)
    
    # Output directory
    cmd.append(str(job.output_dir))
    
    # Max pages
    max_pages = opts.get('max_pages', 100)
    cmd.append(str(max_pages))
    
    # Scroll for infinite scroll pages
    if opts.get('js_scroll', True):
        cmd.append('--scroll')
    
    # Click "Show More" buttons
    if opts.get('js_click_more', True):
        cmd.append('--click-more')
    
    # Wait time for JS rendering
    wait_time = opts.get('js_wait', 2000)
    cmd.append(f'--wait={wait_time}')
    
    # Depth
    depth = opts.get('depth', 3)
    cmd.append(f'--depth={depth}')
    
    return cmd


def run_single_engine(job, engine_name, cmd):
    """Run a single engine and return success status"""
    job.output_lines.append(f"")
    job.output_lines.append(f"{'='*50}")
    job.output_lines.append(f"Running: {engine_name}")
    job.output_lines.append(f"Command: {' '.join(cmd)}")
    job.output_lines.append(f"{'='*50}")
    
    socketio.emit('job_update', job.to_dict())
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        job.process = process
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                job.output_lines.append(line)
                
                update_job_stats(job)
                socketio.emit('job_update', job.to_dict())
        
        process.wait()
        return process.returncode == 0
    except Exception as e:
        job.output_lines.append(f"Error in {engine_name}: {str(e)}")
        return False


def run_wget_job(job_id):
    """Run download job in background (supports multiple engines)"""
    job = jobs.get(job_id)
    if not job:
        return
    
    job.status = 'running'
    job.started_at = datetime.now()
    
    # Smart mode - run all engines sequentially
    if job.engine == 'smart':
        job.output_lines.append("SMART MODE: Running all engines for maximum coverage")
        socketio.emit('job_update', job.to_dict())
        save_jobs()
        
        # Step 1: wget2 for fast static content
        if not job.stop_requested:
            cmd_wget2 = build_wget_command(job)
            run_single_engine(job, "wget2 (static content)", cmd_wget2)
        
        # Step 2: Puppeteer for JS-rendered content
        if not job.stop_requested:
            cmd_puppeteer = build_puppeteer_command(job)
            run_single_engine(job, "Puppeteer (JS rendering)", cmd_puppeteer)
        
        # Step 3: httrack for anything missed
        if not job.stop_requested:
            cmd_httrack = build_httrack_command(job)
            run_single_engine(job, "HTTrack (final pass)", cmd_httrack)
        
        # Finish
        if job.stop_requested:
            job.output_lines.append("")
            job.output_lines.append("SMART MODE STOPPED by user")
        else:
            job.status = 'completed'
            job.finished_at = datetime.now()
            job.output_lines.append("")
            job.output_lines.append("SMART MODE COMPLETED - All engines finished")
        socketio.emit('job_update', job.to_dict())
        save_jobs()
        return
    
    # Single engine mode
    if job.engine == 'puppeteer':
        cmd = build_puppeteer_command(job)
    elif job.engine == 'httrack':
        cmd = build_httrack_command(job)
    else:
        cmd = build_wget_command(job)
    
    job.output_lines.append(f"Engine: {job.engine}")
    job.output_lines.append(f"Command: {' '.join(cmd)}")
    
    socketio.emit('job_update', job.to_dict())
    save_jobs()
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        job.process = process
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                job.output_lines.append(line)
                
                update_job_stats(job)
                socketio.emit('job_update', job.to_dict())
        
        process.wait()
        
        # Post-processing: remove unwanted external domains
        cleanup_external_domains(job)
        
        job.status = 'completed' if process.returncode == 0 else 'failed'
        job.finished_at = datetime.now()
        update_job_stats(job)
        
        # Auto-generate preview screenshot
        if job.status == 'completed':
            try:
                from urllib.parse import urlparse
                parsed = urlparse(job.url)
                main_domain = parsed.netloc.replace('www.', '')
                
                job.output_lines.append("")
                job.output_lines.append("[WCLoner] Создание preview screenshot...")
                
                preview_path = generate_preview_screenshot(
                    folder_path=job.output_dir,
                    main_domain=main_domain,
                    job_id=job.id
                )
                
                if preview_path:
                    job.output_lines.append(f"[WCLoner] ✅ Preview создан: {preview_path.name}")
                    # Сохраняем путь к preview в job
                    job.preview_image = f"/static/previews/{preview_path.name}"
                else:
                    job.output_lines.append("[WCLoner] ⚠️ Preview не создан")
            except Exception as e:
                job.output_lines.append(f"[WCLoner] ❌ Ошибка preview: {str(e)}")
        
        # Auto-generate Vue wrapper if requested
        if job.status == 'completed' and job.options.get('with_vue_wrapper', False):
            try:
                from urllib.parse import urlparse
                parsed = urlparse(job.url)
                main_domain = parsed.netloc.replace('www.', '')
                
                job.output_lines.append("")
                job.output_lines.append("[WCLoner] Генерация Vue-обёртки...")
                
                success = generate_vue_wrapper(
                    folder_path=job.output_dir,
                    main_domain=main_domain,
                    port=3000,
                    backend_port=3001
                )
                
                if success:
                    job.output_lines.append("[WCLoner] ✅ Vue-обёртка создана!")
                    job.output_lines.append(f"[WCLoner] Запуск:")
                    job.output_lines.append(f"[WCLoner]   1. cd {job.output_dir}/vue-app")
                    job.output_lines.append(f"[WCLoner]   2. npm install")
                    job.output_lines.append(f"[WCLoner]   3. node ../backend-server.js (терминал 1)")
                    job.output_lines.append(f"[WCLoner]   4. npm run dev (терминал 2)")
                else:
                    job.output_lines.append("[WCLoner] ⚠️ Ошибка генерации Vue-обёртки")
            except Exception as e:
                job.output_lines.append(f"[WCLoner] ❌ Ошибка генерации: {str(e)}")
        
    except Exception as e:
        job.status = 'failed'
        job.output_lines.append(f"Error: {str(e)}")
        job.finished_at = datetime.now()
    
    socketio.emit('job_update', job.to_dict())
    save_jobs()


def cleanup_external_domains(job):
    """Remove folders of external domains using common filter config"""
    # Use common filter config
    filter_config = get_domain_filter_config(job)
    
    # Check each folder in output directory
    if not job.output_dir.exists():
        return
    
    removed_count = 0
    for folder in job.output_dir.iterdir():
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        
        # Skip special folders
        if folder_name in ('hts-cache', 'hts-log.txt', 'cookies.txt'):
            continue
        
        # Use common is_domain_allowed function
        if not is_domain_allowed(folder_name, filter_config):
            # Remove external domain folder
            try:
                shutil.rmtree(folder)
                removed_count += 1
                job.output_lines.append(f"[Cleanup] Removed external: {folder_name}")
            except Exception as e:
                job.output_lines.append(f"[Cleanup] Error removing {folder_name}: {e}")
    
    if removed_count > 0:
        job.output_lines.append(f"[Cleanup] Removed {removed_count} external domain folders")
        socketio.emit('job_update', job.to_dict())


def format_size(size_bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def update_job_stats(job):
    """Update job file count and total size"""
    try:
        files = list(job.output_dir.rglob('*'))
        job.files_downloaded = sum(1 for f in files if f.is_file())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        job.total_size = format_size(total_size)
    except:
        pass


def start_job_thread(job_id):
    """Start job in background thread"""
    thread = threading.Thread(target=run_wget_job, args=(job_id,))
    thread.daemon = True
    thread.start()


def find_index_file(folder_path):
    """Find index.html or first HTML file in folder"""
    index_files = list(folder_path.rglob('index.html'))
    if index_files:
        return index_files[0]
    html_files = list(folder_path.rglob('*.html'))
    if html_files:
        return html_files[0]
    return None


def extract_domain_from_url(url):
    """Extract clean domain from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def normalize_url(url):
    """Normalize URL for duplicate comparison"""
    parsed = urlparse(url)
    # Remove www., trailing slash, default ports
    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    # Remove default ports
    domain = domain.replace(':80', '').replace(':443', '')
    # Normalize path
    path = parsed.path.rstrip('/') or '/'
    return f"{parsed.scheme}://{domain}{path}"


@app.route('/')
def index():
    return render_template('landings.html', downloads_dir=str(DOWNLOADS_DIR))


@app.route('/old')
def old_index():
    return render_template('index.html', downloads_dir=str(DOWNLOADS_DIR))


@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    return jsonify([job.to_dict() for job in jobs.values()])


@app.route('/api/jobs', methods=['POST'])
def create_job():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Normalize URL for duplicate check
    normalized_url = normalize_url(url)
    
    job_id = str(uuid.uuid4())[:8]
    options = data.get('options', {})
    use_wget2 = data.get('use_wget2', False)
    engine = data.get('engine', 'wget2' if use_wget2 else 'wget')
    
    # Generate folder name from domain + engine (allows different methods for same site)
    domain = extract_domain_from_url(url)
    folder_name = f"{domain}_{engine}"
    
    # Check for duplicate: same URL + same engine already exists
    for existing_job in jobs.values():
        if normalize_url(existing_job.url) == normalized_url and existing_job.engine == engine:
            status_msg = {
                'running': 'is currently being downloaded',
                'pending': 'is pending download',
                'paused': 'is paused',
                'completed': 'was already downloaded',
                'stopped': 'was stopped',
                'failed': 'failed previously'
            }.get(existing_job.status, 'exists')
            return jsonify({
                'error': f'This URL ({engine}) {status_msg}. Delete the existing job first to re-download.',
                'existing_job_id': existing_job.id
            }), 409
    
    job = WgetJob(job_id, url, options, use_wget2, folder_name, engine)
    jobs[job_id] = job
    save_jobs()
    
    start_job_thread(job_id)
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Kill process if running
    if job.process and job.process.poll() is None:
        job.process.terminate()
    
    # Remove output directory
    if job.output_dir.exists():
        shutil.rmtree(job.output_dir)
    
    del jobs[job_id]
    save_jobs()
    return jsonify({'success': True})


@app.route('/api/jobs/<job_id>/stop', methods=['POST'])
def stop_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Set stop flag to break Smart mode loop
    job.stop_requested = True
    
    if job.process and job.process.poll() is None:
        job.process.terminate()
        try:
            job.process.wait(timeout=2)
        except:
            job.process.kill()
    
    job.status = 'stopped'
    job.finished_at = datetime.now()
    save_jobs()
    socketio.emit('job_update', job.to_dict())
    
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>/pause', methods=['POST'])
def pause_job(job_id):
    """Pause a running job using SIGSTOP"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.status != 'running':
        return jsonify({'error': 'Job is not running', 'status': job.status}), 400
    
    if job.process and job.process.poll() is None:
        try:
            job.process.send_signal(signal.SIGSTOP)
            job.status = 'paused'
            job.output_lines.append("[PAUSED by user]")
            socketio.emit('job_update', job.to_dict())
            save_jobs()
        except Exception as e:
            return jsonify({'error': f'Failed to pause: {str(e)}'}), 500
    else:
        return jsonify({'error': 'No active process to pause'}), 400
    
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>/resume', methods=['POST'])
def resume_job(job_id):
    """Resume a paused job using SIGCONT"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.process and job.process.poll() is None and job.status == 'paused':
        job.process.send_signal(signal.SIGCONT)
        job.status = 'running'
        socketio.emit('job_update', job.to_dict())
        save_jobs()
    
    return jsonify(job.to_dict())


@app.route('/api/jobs/<job_id>/restart', methods=['POST'])
def restart_job(job_id):
    """Restart a job with same URL and options"""
    old_job = jobs.get(job_id)
    if not old_job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Stop if still running
    if old_job.process and old_job.process.poll() is None:
        old_job.process.terminate()
    
    # Get engine from request or use old job's engine
    data = request.json or {}
    engine = data.get('engine', old_job.engine)
    use_wget2 = data.get('use_wget2', old_job.use_wget2)
    
    # Copy options and update extra_domains if provided
    new_options = old_job.options.copy()
    if data.get('extra_domains'):
        new_options['extra_domains'] = data['extra_domains']
        new_options['include_subdomains'] = True
    
    # Create new job with selected engine
    new_job_id = str(uuid.uuid4())[:8]
    new_job = WgetJob(new_job_id, old_job.url, new_options, use_wget2, old_job.folder_name, engine)
    new_job.options['continue_download'] = True  # Resume mode
    jobs[new_job_id] = new_job
    
    # Remove old job
    del jobs[job_id]
    save_jobs()
    
    start_job_thread(new_job_id)
    return jsonify(new_job.to_dict())


@app.route('/api/jobs/<job_id>/files')
def get_job_files(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    files = []
    for f in job.output_dir.rglob('*'):
        if f.is_file():
            rel_path = f.relative_to(job.output_dir)
            files.append({
                'path': str(rel_path),
                'size': format_size(f.stat().st_size),
                'type': f.suffix[1:] if f.suffix else 'file'
            })
    
    return jsonify(files)


@app.route('/api/jobs/<job_id>/download')
def download_job(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Create zip archive
    zip_path = DOWNLOADS_DIR / f"{job_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', job.output_dir)
    
    return send_file(zip_path, as_attachment=True, download_name=f"wget-{job_id}.zip")


@app.route('/api/jobs/<job_id>/browse/<path:filepath>')
def browse_file(job_id, filepath):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    file_path = job.output_dir / filepath
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_from_directory(job.output_dir, filepath)


@app.route('/api/jobs/<job_id>/open')
def open_in_browser(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    index_file = find_index_file(job.output_dir)
    if index_file:
        os.system(f'open "{index_file}"')
        return jsonify({'success': True, 'file': str(index_file)})
    
    return jsonify({'error': 'No HTML files found'}), 404


@app.route('/api/jobs/<job_id>/open-folder')
def open_folder(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    os.system(f'open "{job.output_dir}"')
    return jsonify({'success': True, 'path': str(job.output_dir)})


@app.route('/api/config')
def get_config():
    wget2_available = os.path.exists(WGET2_PATH)
    return jsonify({
        'downloads_dir': str(DOWNLOADS_DIR),
        'wget2_path': WGET2_PATH,
        'wget2_available': wget2_available
    })


@app.route('/api/open-downloads')
def open_downloads_folder():
    os.system(f'open "{DOWNLOADS_DIR}"')
    return jsonify({'success': True, 'path': str(DOWNLOADS_DIR)})


@app.route('/api/open-folder')
def open_any_folder():
    path = request.args.get('path', '')
    if path and os.path.exists(path):
        os.system(f'open "{path}"')
        return jsonify({'success': True})
    return jsonify({'error': 'Path not found'}), 404


@app.route('/api/open-site')
def open_site_in_browser():
    path = request.args.get('path', '')
    if path and os.path.exists(path):
        index_file = find_index_file(Path(path))
        if index_file:
            os.system(f'open "{index_file}"')
            return jsonify({'success': True, 'file': str(index_file)})
        # If no HTML files, just open folder
        os.system(f'open "{path}"')
        return jsonify({'success': True, 'opened': 'folder'})
    return jsonify({'error': 'Path not found'}), 404


@app.route('/api/downloads')
def list_downloads():
    """List all downloaded folders in downloads directory"""
    # Get list of folders currently being downloaded
    active_folders = set()
    for job in jobs.values():
        if job.status in ('running', 'pending', 'paused'):
            active_folders.add(job.folder_name)
    
    downloads = []
    for item in DOWNLOADS_DIR.iterdir():
        if item.is_dir():
            # Calculate folder size and file count
            files = list(item.rglob('*'))
            file_count = sum(1 for f in files if f.is_file())
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            
            # Get modification time
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            
            # Check if currently downloading
            is_active = item.name in active_folders
            status = 'downloading' if is_active else 'completed'
            
            downloads.append({
                'name': item.name,
                'path': str(item),
                'files': file_count,
                'size': format_size(total_size),
                'date': mtime.strftime('%Y-%m-%d %H:%M'),
                'status': status,
                'is_active': is_active
            })
    
    # Sort by date descending
    downloads.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(downloads)


@app.route('/api/file-tree/<folder_name>')
def get_file_tree(folder_name):
    """Get full file tree for a downloaded site folder with stats"""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    # Collect all files
    files = []
    stats = {'html': 0, 'css': 0, 'js': 0, 'images': 0, 'other': 0, 'total_files': 0, 'total_size': 0}
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico', '.bmp'}
    
    for f in folder_path.rglob('*'):
        if not f.is_file():
            continue
        if '_wcloner' in str(f):
            continue
        
        rel_path = str(f.relative_to(folder_path))
        size = f.stat().st_size
        ext = f.suffix.lower()
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        
        # Determine file type
        if ext in ('.html', '.htm'):
            ftype = 'html'
        elif ext in ('.css',):
            ftype = 'css'
        elif ext in ('.js', '.mjs'):
            ftype = 'js'
        elif ext in image_exts:
            ftype = 'image'
        else:
            ftype = 'other'
        
        # Count stats
        if ftype == 'html':
            stats['html'] += 1
        elif ftype == 'css':
            stats['css'] += 1
        elif ftype == 'js':
            stats['js'] += 1
        elif ftype == 'image':
            stats['images'] += 1
        else:
            stats['other'] += 1
        stats['total_files'] += 1
        stats['total_size'] += size
        
        files.append({
            'path': rel_path,
            'name': f.name,
            'size': format_size(size),
            'size_bytes': size,
            'date': mtime,
            'type': ftype,
            'ext': ext
        })
    
    stats['total_size_formatted'] = format_size(stats['total_size'])
    
    return jsonify({
        'folder_name': folder_name,
        'files': files,
        'stats': stats
    })


@app.route('/api/browse/<path:filepath>')
def browse_download(filepath):
    """Serve files from downloads directory for built-in viewer"""
    return send_from_directory(DOWNLOADS_DIR, filepath)


@app.route('/api/downloads/<folder_name>', methods=['DELETE'])
def delete_download(folder_name):
    """Delete a downloaded folder"""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    try:
        shutil.rmtree(folder_path)
        return jsonify({'success': True, 'deleted': folder_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/downloads/<folder_name>/continue', methods=['POST'])
def continue_download(folder_name):
    """Continue downloading an existing folder (resume incomplete download)"""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    data = request.json or {}
    
    # Extract domain from folder name (format: domain_timestamp)
    parts = folder_name.split('_')
    domain = '_'.join(parts[:-2]) if len(parts) > 2 else parts[0]
    url = data.get('url', f'https://{domain}')
    
    # Default options for continue (with timestamping for resume)
    options = data.get('options', {
        'recursive': True,
        'depth': 5,
        'page_requisites': True,
        'convert_links': True,
        'no_parent': True,
        'include_subdomains': True,
        'ignore_robots': True
    })
    
    use_wget2 = data.get('use_wget2', False)
    
    engine = data.get('engine', 'smart')
    job_id = str(uuid.uuid4())[:8]
    job = WgetJob(job_id, url, options, use_wget2, folder_name, engine)
    job.options['continue_download'] = True
    jobs[job_id] = job
    
    start_job_thread(job_id)
    return jsonify(job.to_dict())


@app.route('/api/downloads/<folder_name>/restart', methods=['POST'])
def restart_download(folder_name):
    """Restart download from scratch (delete and re-download)"""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    data = request.json or {}
    
    # Extract domain from folder name
    parts = folder_name.split('_')
    domain = '_'.join(parts[:-2]) if len(parts) > 2 else parts[0]
    url = data.get('url', f'https://{domain}')
    
    # Delete existing folder
    shutil.rmtree(folder_path)
    
    # Default options for full re-download
    options = data.get('options', {
        'recursive': True,
        'depth': 5,
        'page_requisites': True,
        'convert_links': True,
        'no_parent': True,
        'include_subdomains': True,
        'ignore_robots': True,
        'mirror_mode': True
    })
    
    use_wget2 = data.get('use_wget2', True)
    engine = data.get('engine', 'smart')
    
    job_id = str(uuid.uuid4())[:8]
    job = WgetJob(job_id, url, options, use_wget2, folder_name, engine)
    jobs[job_id] = job
    
    start_job_thread(job_id)
    return jsonify(job.to_dict())


@app.route('/api/jobs/active')
def get_active_jobs():
    """Get only running jobs for active downloads display"""
    active = [job.to_dict() for job in jobs.values() if job.status in ('pending', 'running')]
    return jsonify(active)


@app.route('/api/find-index/<folder_name>')
def find_index_html_api(folder_name):
    """Find index.html in a download folder"""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    index_file = find_index_file(folder_path)
    if index_file:
        # Return path relative to folder_path, not DOWNLOADS_DIR
        rel_path = index_file.relative_to(folder_path)
        return jsonify({'index_path': str(rel_path)})
    
    return jsonify({'error': 'No HTML files found'}), 404


@app.route('/api/scan', methods=['POST'])
def scan_site():
    """Scan a website to find all subdomains and create a link map"""
    import requests
    from bs4 import BeautifulSoup
    import re
    
    data = request.json
    url = data.get('url', '').strip()
    max_pages = data.get('max_pages', 50)
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed = urlparse(url)
    base_domain = parsed.netloc
    if base_domain.startswith('www.'):
        base_domain = base_domain[4:]
    
    # Extract root domain (last 2 parts)
    domain_parts = base_domain.split('.')
    if len(domain_parts) >= 2:
        root_domain = '.'.join(domain_parts[-2:])
    else:
        root_domain = base_domain
    
    # Extract brand name for finding related domains (e.g., "arianagrande" from "arianagrande.com")
    brand_name = domain_parts[0] if domain_parts else base_domain
    
    visited = set()
    subdomains = {}  # {subdomain: {'count': N, 'sample_urls': []}}
    related_domains = {}  # Domains containing brand name
    cdn_domains = {}  # CDN domains (shopify, cloudflare, etc.)
    external_domains = {}  # Other external domains
    to_visit = [url]
    
    # Known CDN patterns
    cdn_patterns = [
        'cdn.', 'static.', 'assets.', 'media.', 'images.', 'img.',
        'shopify.com', 'shopifycdn.com', 'cloudflare.com', 'cloudfront.net',
        'amazonaws.com', 's3.', 'googleapis.com', 'gstatic.com',
        'jsdelivr.net', 'unpkg.com', 'cdnjs.', 'bootstrapcdn.com',
        'fontawesome.com', 'fonts.google', 'typekit.net',
        'akamai', 'fastly', 'cloudinary.com', 'imgix.net'
    ]
    
    # Known external/tracking domains to categorize separately
    external_patterns = [
        'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com',
        'google.com', 'googletagmanager.com', 'google-analytics.com',
        'linkedin.com', 'pinterest.com', 'tiktok.com',
        'doubleclick.net', 'adsrvr.org', 'adroll.com'
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    pages_scanned = 0
    
    while to_visit and pages_scanned < max_pages:
        current_url = to_visit.pop(0)
        if current_url in visited:
            continue
        
        visited.add(current_url)
        pages_scanned += 1
        
        try:
            response = requests.get(current_url, headers=headers, timeout=20, allow_redirects=True)
            if response.status_code != 200:
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'source']):
                href = tag.get('href') or tag.get('src')
                if not href:
                    continue
                
                # Make absolute URL
                if href.startswith('//'):
                    href = 'https:' + href
                elif href.startswith('/'):
                    href = f"{parsed.scheme}://{parsed.netloc}{href}"
                elif not href.startswith(('http://', 'https://')):
                    continue
                
                try:
                    link_parsed = urlparse(href)
                    link_domain = link_parsed.netloc
                    if not link_domain:
                        continue
                    
                    # Determine domain category
                    is_subdomain = link_domain.endswith(root_domain) or link_domain == root_domain
                    is_related = brand_name.lower() in link_domain.lower() and len(brand_name) >= 4
                    is_cdn = any(p in link_domain.lower() for p in cdn_patterns)
                    is_external = any(p in link_domain.lower() for p in external_patterns)
                    
                    # Helper to add domain to dict
                    def add_to_dict(d, domain, is_main=False):
                        if domain not in d:
                            d[domain] = {'count': 0, 'sample_urls': [], 'is_main': is_main}
                        d[domain]['count'] += 1
                        if len(d[domain]['sample_urls']) < 3:
                            clean_url = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path}"
                            if clean_url not in d[domain]['sample_urls']:
                                d[domain]['sample_urls'].append(clean_url)
                    
                    if is_subdomain:
                        is_main = link_domain == parsed.netloc or link_domain == base_domain or link_domain == f'www.{base_domain}'
                        add_to_dict(subdomains, link_domain, is_main)
                        # Add to visit queue if same main domain
                        if link_domain == parsed.netloc and href not in visited:
                            to_visit.append(href)
                    elif is_related:
                        add_to_dict(related_domains, link_domain)
                    elif is_cdn:
                        add_to_dict(cdn_domains, link_domain)
                    elif is_external:
                        add_to_dict(external_domains, link_domain)
                    else:
                        # Other external domains
                        add_to_dict(external_domains, link_domain)
                except:
                    continue
                    
        except Exception as e:
            print(f"[Scan] Error fetching {current_url}: {e}")
            continue
    
    # Convert to categorized lists
    def to_list(d, domain_type):
        return sorted([{
            'domain': domain,
            'count': info['count'],
            'sample_urls': info['sample_urls'],
            'is_main': info.get('is_main', False),
            'type': domain_type
        } for domain, info in d.items()], key=lambda x: (-x['is_main'], -x['count']))
    
    main_domains = to_list(subdomains, 'main')
    related_list = to_list(related_domains, 'related')
    cdn_list = to_list(cdn_domains, 'cdn')
    external_list = to_list(external_domains, 'external')
    
    # Combined list for backward compatibility
    all_domains = main_domains + related_list + cdn_list + external_list
    
    return jsonify({
        'base_domain': base_domain,
        'root_domain': root_domain,
        'brand_name': brand_name,
        'pages_scanned': pages_scanned,
        'subdomains': all_domains,  # backward compatibility
        'categories': {
            'main': main_domains,
            'related': related_list,
            'cdn': cdn_list,
            'external': external_list
        },
        'counts': {
            'main': len(main_domains),
            'related': len(related_list),
            'cdn': len(cdn_list),
            'external': len(external_list)
        }
    })


# =============================================================================
# LANDING MANAGER - Page and API
# =============================================================================

LANDINGS_CONFIG_FILE = BASE_DIR / 'admin' / 'landings.json'


def load_landings_config():
    """Load individual landing settings"""
    if not LANDINGS_CONFIG_FILE.exists():
        return {}
    try:
        with open(LANDINGS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_landings_config(config):
    """Save individual landing settings"""
    try:
        with open(LANDINGS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving landings config: {e}")


@app.route('/landings')
def landings_page():
    return render_template('landings.html', downloads_dir=str(DOWNLOADS_DIR))


@app.route('/index')
def index_page():
    return render_template('index.html', downloads_dir=str(DOWNLOADS_DIR))


@app.route('/api/landings')
def get_landings():
    """Get all downloads grouped by parent domain -> subdomains"""
    import re
    
    landings_config = load_landings_config()
    
    # Active folders
    active_folders = set()
    for job in jobs.values():
        if job.status in ('running', 'pending', 'paused'):
            active_folders.add(job.folder_name)
    
    # Collect all downloaded folders
    domains_map = {}  # parent_domain -> {subdomains, pages, settings}
    
    for item in DOWNLOADS_DIR.iterdir():
        if not item.is_dir():
            continue
        
        folder_name = item.name
        
        # Parse folder name: domain_engine or just domain
        parts = folder_name.rsplit('_', 1)
        engine = parts[1] if len(parts) > 1 and parts[1] in ('wget2', 'httrack', 'puppeteer', 'smart') else 'unknown'
        domain_part = parts[0] if engine != 'unknown' else folder_name
        
        # Extract parent domain (last 2 parts: example.com)
        domain_parts = domain_part.split('.')
        if len(domain_parts) >= 2:
            parent_domain = '.'.join(domain_parts[-2:])
        else:
            parent_domain = domain_part
        
        # Calc stats
        all_files = list(item.rglob('*'))
        file_count = sum(1 for f in all_files if f.is_file())
        total_size = sum(f.stat().st_size for f in all_files if f.is_file())
        mtime = datetime.fromtimestamp(item.stat().st_mtime)
        
        # Collect HTML pages at folder root level (not inside subdomain dirs)
        root_pages = []
        for html_file in item.rglob('*.html'):
            rel_path = str(html_file.relative_to(item))
            root_pages.append({
                'name': html_file.name,
                'path': rel_path,
                'full_path': str(html_file),
                'size': format_size(html_file.stat().st_size),
                'size_bytes': html_file.stat().st_size,
                'date': datetime.fromtimestamp(html_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                'subdomain': rel_path.split(os.sep)[0] if os.sep in rel_path else ''
            })
        
        # Find subdomains inside the folder
        subdomains = []
        for sub in item.iterdir():
            if sub.is_dir() and '.' in sub.name and sub.name not in ('hts-cache', '_next', 'static', 'assets', 'images', 'css', 'js', 'fonts'):
                sub_files = list(sub.rglob('*'))
                sub_file_count = sum(1 for f in sub_files if f.is_file())
                sub_size = sum(f.stat().st_size for f in sub_files if f.is_file())
                sub_mtime = datetime.fromtimestamp(sub.stat().st_mtime)
                
                # Find HTML pages in subdomain
                html_pages = []
                for html_file in sub.rglob('*.html'):
                    rel_path = str(html_file.relative_to(item))
                    html_pages.append({
                        'name': html_file.name,
                        'path': rel_path,
                        'size': format_size(html_file.stat().st_size),
                        'date': datetime.fromtimestamp(html_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                    })
                
                # Individual settings for this subdomain
                config_key = f"{folder_name}/{sub.name}"
                sub_config = landings_config.get(config_key, {})
                
                subdomains.append({
                    'name': sub.name,
                    'files': sub_file_count,
                    'size': format_size(sub_size),
                    'date': sub_mtime.strftime('%Y-%m-%d %H:%M'),
                    'pages': html_pages,
                    'config': sub_config,
                    'config_key': config_key
                })
        
        subdomains.sort(key=lambda x: x['name'])
        
        is_active = folder_name in active_folders
        
        # Find related job
        related_job = None
        for job in jobs.values():
            if job.folder_name == folder_name:
                related_job = {
                    'id': job.id,
                    'status': job.status,
                    'engine': job.engine,
                    'url': job.url
                }
                break
        
        # Individual config for this folder
        folder_config = landings_config.get(folder_name, {})
        
        # Group under parent domain
        if parent_domain not in domains_map:
            domains_map[parent_domain] = {
                'parent_domain': parent_domain,
                'folders': [],
                'total_files': 0,
                'total_size': 0,
            }
        
        domains_map[parent_domain]['folders'].append({
            'folder_name': folder_name,
            'domain': domain_part,
            'engine': engine,
            'path': str(item),
            'files': file_count,
            'size': format_size(total_size),
            'size_bytes': total_size,
            'date': mtime.strftime('%Y-%m-%d %H:%M'),
            'is_active': is_active,
            'subdomains': subdomains,
            'pages': root_pages,
            'job': related_job,
            'config': folder_config
        })
        domains_map[parent_domain]['total_files'] += file_count
        domains_map[parent_domain]['total_size'] += total_size
    
    # Format and sort
    result = []
    for pd, data in domains_map.items():
        data['total_size_formatted'] = format_size(data['total_size'])
        data['folders'].sort(key=lambda x: x['date'], reverse=True)
        result.append(data)
    
    result.sort(key=lambda x: x['parent_domain'])
    return jsonify(result)


@app.route('/api/landings/config', methods=['POST'])
def save_landing_config():
    """Save individual settings for a landing/subdomain"""
    data = request.json
    config_key = data.get('config_key', '')
    settings = data.get('settings', {})
    
    if not config_key:
        return jsonify({'error': 'config_key is required'}), 400
    
    landings_config = load_landings_config()
    landings_config[config_key] = settings
    save_landings_config(landings_config)
    
    return jsonify({'success': True, 'config_key': config_key})


@app.route('/api/check-changes/<folder_name>', methods=['GET'])
def check_changes_endpoint(folder_name):
    """Quick check if site has changes. Supports ?subdomain=X and ?page=path/to/file.html"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    subdomain = request.args.get('subdomain', '').strip()
    page_path = request.args.get('page', '').strip()
    
    # Пытаемся найти URL из конфига или job
    url = None
    
    # Проверяем активные jobs
    for job in jobs.values():
        if job.folder_name == folder_name:
            url = job.url
            break
    
    # Если не нашли в jobs, ищем в конфиге
    if not url:
        config_path = folder_path / '_wcloner' / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    url = config_data.get('original_url')
            except Exception:
                pass
    
    # Если не нашли в jobs, пытаемся определить из имени папки
    if not url:
        url = f"https://{folder_name}"
    
    # Проверка конкретной страницы
    if page_path:
        result = check_page_changes(folder_path, url, page_path)
        return jsonify(result)
    
    # Проверка поддомена
    if subdomain:
        sub_url = f"https://{subdomain}"
        sub_folder = folder_path / subdomain
        if sub_folder.exists():
            result = check_site_changes(sub_folder, sub_url)
            result['subdomain'] = subdomain
            return jsonify(result)
        else:
            return jsonify({'error': f'Subdomain folder not found: {subdomain}', 'has_changes': False})
    
    result = check_site_changes(folder_path, url)
    return jsonify(result)


@app.route('/api/check-all-changes/<folder_name>', methods=['GET'])
def check_all_changes_endpoint(folder_name):
    """Check all HTML pages for changes compared to online versions"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    max_pages = request.args.get('max', 50, type=int)
    
    # Get base URL
    url = None
    for job in jobs.values():
        if job.folder_name == folder_name:
            url = job.url
            break
    
    if not url:
        config_path = folder_path / '_wcloner' / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    url = config_data.get('original_url')
            except:
                pass
    
    if not url:
        url = f"https://{folder_name}"
    
    result = check_all_pages_changes(folder_path, url, max_pages)
    result['folder_name'] = folder_name
    result['base_url'] = url
    return jsonify(result)


@app.route('/api/check-integrity/<folder_name>', methods=['GET'])
def check_integrity_endpoint(folder_name):
    """Check site integrity - find missing referenced resources"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    result = check_site_integrity(folder_path)
    result['folder_name'] = folder_name
    return jsonify(result)


@app.route('/api/download-missing/<folder_name>', methods=['POST'])
def download_missing_endpoint(folder_name):
    """Download missing files for a site"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    data = request.json or {}
    missing_paths = data.get('paths', [])
    
    if not missing_paths:
        return jsonify({'error': 'No paths provided'}), 400
    
    # Determine base URL
    url = None
    for job in jobs.values():
        if job.folder_name == folder_name:
            url = job.url
            break
    
    if not url:
        config_path = folder_path / '_wcloner' / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    url = config_data.get('original_url')
            except Exception:
                pass
    
    if not url:
        url = f"https://{folder_name}"
    
    result = download_missing_files(folder_path, url, missing_paths)
    return jsonify(result)


@app.route('/api/thumbnail/<folder_name>')
def get_thumbnail(folder_name):
    """Get thumbnail/preview image for a site"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    # Check for preview in site folder
    preview_path = folder_path / 'preview.png'
    if preview_path.exists():
        return send_file(preview_path, mimetype='image/png')
    
    # Check in previews directory
    preview_in_dir = PREVIEWS_DIR / f"{folder_name}.png"
    if preview_in_dir.exists():
        return send_file(preview_in_dir, mimetype='image/png')
    
    # Return 404 if no preview
    return jsonify({'error': 'No preview available'}), 404


@app.route('/api/screenshot/<folder_name>', methods=['POST'])
def create_screenshot(folder_name):
    """Create screenshot for a downloaded site"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return jsonify({'error': 'Folder not found'}), 404
    
    try:
        # Find index.html
        index_file = find_index_file(folder_path)
        if not index_file:
            return jsonify({'error': 'No index.html found'}), 404
        
        # Get domain from folder name
        main_domain = folder_name.split('_')[0] if '_' in folder_name else folder_name
        
        preview_path = generate_preview_screenshot(
            folder_path=folder_path,
            main_domain=main_domain,
            job_id=folder_name,
            index_file=index_file
        )
        
        if preview_path and preview_path.exists():
            return jsonify({'success': True, 'path': str(preview_path)})
        else:
            return jsonify({'error': 'Failed to generate screenshot'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/landings/analyze', methods=['POST'])
def analyze_changes():
    """Compare original site with our downloaded copy"""
    import requests as req
    from bs4 import BeautifulSoup
    import hashlib
    
    data = request.json
    url = data.get('url', '').strip()
    folder_path = data.get('folder_path', '').strip()
    subdomain = data.get('subdomain', '').strip()
    
    if not url or not folder_path:
        return jsonify({'error': 'url and folder_path required'}), 400
    
    local_dir = Path(folder_path)
    if subdomain:
        local_dir = local_dir / subdomain
    
    if not local_dir.exists():
        return jsonify({'error': 'Local folder not found'}), 404
    
    changes = {
        'modified': [],
        'new_on_remote': [],
        'only_local': [],
        'unchanged': [],
        'errors': []
    }
    
    # Find all local HTML files
    local_html = {}
    for html_file in local_dir.rglob('*.html'):
        rel = str(html_file.relative_to(local_dir))
        with open(html_file, 'r', errors='ignore') as f:
            content = f.read()
        local_html[rel] = {
            'path': rel,
            'size': html_file.stat().st_size,
            'hash': hashlib.md5(content.encode()).hexdigest(),
            'date': datetime.fromtimestamp(html_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        }
    
    # Fetch remote pages and compare
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # Check main page
    try:
        resp = req.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            remote_hash = hashlib.md5(resp.text.encode()).hexdigest()
            remote_size = len(resp.text)
            
            # Find matching local file
            matched = False
            for rel_path, local_info in local_html.items():
                if 'index' in rel_path.lower():
                    matched = True
                    if local_info['hash'] != remote_hash:
                        changes['modified'].append({
                            'page': url,
                            'local_path': rel_path,
                            'local_size': format_size(local_info['size']),
                            'remote_size': format_size(remote_size),
                            'local_date': local_info['date']
                        })
                    else:
                        changes['unchanged'].append({
                            'page': url,
                            'local_path': rel_path
                        })
                    break
            
            if not matched:
                changes['new_on_remote'].append({
                    'page': url,
                    'size': format_size(remote_size)
                })
            
            # Parse links from remote page
            soup = BeautifulSoup(resp.text, 'html.parser')
            parsed_url = urlparse(url)
            base = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/') and not href.startswith('//'):
                    full_url = base + href
                    # Check if we have this page locally
                    possible_local = href.strip('/').replace('/', os.sep)
                    if possible_local and not any(possible_local in lp for lp in local_html):
                        changes['new_on_remote'].append({
                            'page': full_url,
                            'size': 'unknown'
                        })
    except Exception as e:
        changes['errors'].append(f"Error fetching {url}: {str(e)}")
    
    # Pages only in local
    for rel_path, info in local_html.items():
        found_in_changes = False
        for c in changes['modified'] + changes['unchanged']:
            if c.get('local_path') == rel_path:
                found_in_changes = True
                break
        if not found_in_changes:
            changes['only_local'].append({
                'local_path': rel_path,
                'size': format_size(info['size']),
                'date': info['date']
            })
    
    summary = {
        'modified': len(changes['modified']),
        'new_on_remote': len(changes['new_on_remote']),
        'only_local': len(changes['only_local']),
        'unchanged': len(changes['unchanged']),
        'errors': len(changes['errors'])
    }
    
    return jsonify({'changes': changes, 'summary': summary})


@app.route('/api/landings/redownload', methods=['POST'])
def redownload_landing():
    """Re-download a specific page or subdomain with individual settings"""
    data = request.json
    url = data.get('url', '').strip()
    folder_name = data.get('folder_name', '').strip()
    config_key = data.get('config_key', '')
    
    if not url or not folder_name:
        return jsonify({'error': 'url and folder_name required'}), 400
    
    # Load individual settings
    landings_config = load_landings_config()
    settings = landings_config.get(config_key, {})
    
    # Merge with defaults
    options = {
        'recursive': True,
        'depth': settings.get('depth', 2),
        'page_requisites': True,
        'convert_links': True,
        'no_parent': True,
        'wait': settings.get('wait', 0.5),
        'include_subdomains': settings.get('include_subdomains', True),
        'extra_domains': settings.get('extra_domains', ''),
        'user_agent': settings.get('user_agent', ''),
        'continue_download': True
    }
    
    engine = settings.get('engine', 'wget2')
    
    job_id = str(uuid.uuid4())[:8]
    job = WgetJob(job_id, url, options, True, folder_name, engine)
    jobs[job_id] = job
    save_jobs()
    
    start_job_thread(job_id)
    return jsonify(job.to_dict())


@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'ok'})


if __name__ == '__main__':
    print(f"Wget Admin starting...")
    print(f"Using wget2: {WGET2_PATH}")
    print(f"Downloads dir: {DOWNLOADS_DIR}")
    load_jobs()  # Load saved jobs on startup
    app.run(host='0.0.0.0', port=8888, debug=True)
