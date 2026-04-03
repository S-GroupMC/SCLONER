"""
Analyzer module - site scanning and change detection
"""
import json
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

from .config import DOWNLOADS_DIR, active_scans
from .constants import DEFAULT_HEADERS, DEFAULT_TIMEOUT


def check_site_changes(folder_path, url):
    """Check if the live site has changes compared to downloaded version"""
    import requests
    from bs4 import BeautifulSoup
    
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    hashes_file = folder_path / '_wcloner' / 'file_hashes.json'
    
    try:
        if hashes_file.exists():
            with open(hashes_file, 'r') as f:
                saved_hashes = json.load(f)
        else:
            saved_hashes = {}
            for file_path in folder_path.rglob('*'):
                if file_path.is_file() and '_wcloner' not in str(file_path):
                    rel_path = str(file_path.relative_to(folder_path))
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    saved_hashes[rel_path] = file_hash
            
            hashes_file.parent.mkdir(exist_ok=True)
            with open(hashes_file, 'w') as f:
                json.dump(saved_hashes, f, indent=2)
        
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        
        if response.status_code != 200:
            return {
                'error': f'HTTP {response.status_code}',
                'has_changes': False
            }
        
        online_hash = hashlib.md5(response.content).hexdigest()
        
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
            try:
                online_soup = BeautifulSoup(response.content, 'html.parser')
                with open(local_index, 'r', encoding='utf-8') as f:
                    local_soup = BeautifulSoup(f.read(), 'html.parser')
                
                online_title = online_soup.title.string if online_soup.title else ''
                local_title = local_soup.title.string if local_soup.title else ''
                
                result['title_changed'] = online_title != local_title
                result['online_title'] = online_title
                result['local_title'] = local_title
                result['online_elements'] = len(online_soup.find_all())
                result['local_elements'] = len(local_soup.find_all())
                
            except Exception as e:
                print(f"[Changes] Error parsing HTML: {e}")
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'has_changes': False
        }


def check_page_changes(folder_path, base_url, page_path):
    """Check if a specific page has changes compared to the online version."""
    import requests
    from bs4 import BeautifulSoup
    
    folder_path = Path(folder_path)
    local_file = folder_path / page_path
    
    if not local_file.exists():
        return {
            'page': page_path,
            'error': 'Local file not found',
            'has_changes': False
        }
    
    try:
        page_url = urljoin(base_url, page_path.replace('.html', '').replace('index', ''))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(page_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                'page': page_path,
                'url': page_url,
                'error': f'HTTP {response.status_code}',
                'has_changes': False
            }
        
        online_hash = hashlib.md5(response.content).hexdigest()
        
        with open(local_file, 'rb') as f:
            local_hash = hashlib.md5(f.read()).hexdigest()
        
        has_changes = online_hash != local_hash
        
        return {
            'page': page_path,
            'url': page_url,
            'has_changes': has_changes,
            'online_hash': online_hash,
            'local_hash': local_hash,
            'checked_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            'page': page_path,
            'error': str(e),
            'has_changes': False
        }


def check_all_pages_changes(folder_path, base_url, max_pages=50):
    """Check all HTML pages for changes"""
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return {'error': 'Folder not found', 'pages': []}
    
    html_files = list(folder_path.rglob('*.html'))[:max_pages]
    
    results = {
        'total_pages': len(html_files),
        'checked': 0,
        'changed': 0,
        'unchanged': 0,
        'errors': 0,
        'pages': []
    }
    
    for html_file in html_files:
        rel_path = str(html_file.relative_to(folder_path))
        
        if '_wcloner' in rel_path or 'vue-app' in rel_path:
            continue
        
        page_result = check_page_changes(folder_path, base_url, rel_path)
        results['pages'].append(page_result)
        results['checked'] += 1
        
        if page_result.get('error'):
            results['errors'] += 1
        elif page_result.get('has_changes'):
            results['changed'] += 1
        else:
            results['unchanged'] += 1
    
    results['has_changes'] = results['changed'] > 0
    
    return results


def check_site_integrity(folder_path):
    """Check site integrity - find missing files, broken links, etc."""
    import re
    
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    result = {
        'total_files': 0,
        'html_files': 0,
        'css_files': 0,
        'js_files': 0,
        'image_files': 0,
        'missing_files': [],
        'broken_links': [],
        'external_links': [],
        'total_size': 0
    }
    
    all_files = set()
    for f in folder_path.rglob('*'):
        if f.is_file() and '_wcloner' not in str(f) and 'vue-app' not in str(f):
            all_files.add(str(f.relative_to(folder_path)))
            result['total_files'] += 1
            result['total_size'] += f.stat().st_size
            
            ext = f.suffix.lower()
            if ext in ['.html', '.htm']:
                result['html_files'] += 1
            elif ext == '.css':
                result['css_files'] += 1
            elif ext == '.js':
                result['js_files'] += 1
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico']:
                result['image_files'] += 1
    
    # Check HTML files for broken links
    for html_file in folder_path.rglob('*.html'):
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file):
            continue
        
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find all href and src attributes
            links = re.findall(r'(?:href|src)=["\']([^"\']+)["\']', content)
            
            for link in links:
                if link.startswith(('http://', 'https://', '//', 'data:', 'javascript:', 'mailto:', '#')):
                    if link.startswith(('http://', 'https://')):
                        result['external_links'].append({
                            'file': str(html_file.relative_to(folder_path)),
                            'link': link
                        })
                    continue
                
                # Resolve relative path
                if link.startswith('/'):
                    target = link[1:]
                else:
                    target = str((html_file.parent / link).relative_to(folder_path))
                
                # Remove query strings and fragments
                target = target.split('?')[0].split('#')[0]
                
                if target and target not in all_files:
                    result['missing_files'].append({
                        'file': str(html_file.relative_to(folder_path)),
                        'missing': target
                    })
        except Exception as e:
            pass
    
    # Deduplicate
    seen_missing = set()
    unique_missing = []
    for m in result['missing_files']:
        key = m['missing']
        if key not in seen_missing:
            seen_missing.add(key)
            unique_missing.append(m)
    result['missing_files'] = unique_missing[:100]
    
    from .utils import format_size
    result['total_size_formatted'] = format_size(result['total_size'])
    
    return result


def _extract_all_urls_from_html(html_text, base_url):
    """
    Извлекает ВСЕ URL из HTML: теги, атрибуты, CSS url(), inline styles,
    srcset, meta content, скрипты — полный парсинг.
    Возвращает список абсолютных URL.
    """
    import re
    from bs4 import BeautifulSoup
    
    parsed_base = urlparse(base_url)
    urls = set()
    
    def normalize_url(href):
        """Нормализует URL в абсолютный"""
        if not href or len(href) < 3:
            return None
        href = href.strip()
        if href.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '#', '{', '$', 'blob:')):
            return None
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        elif not href.startswith(('http://', 'https://')):
            return None
        # Убираем мусор в конце
        href = href.rstrip('.,;:!?)]\'"')
        return href if len(href) > 10 else None
    
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # 1. Все теги с URL-атрибутами
    url_attrs = ['href', 'src', 'data-src', 'data-href', 'data-url', 'data-image',
                 'data-background', 'data-poster', 'data-bg', 'data-lazy-src',
                 'data-original', 'data-srcset', 'poster', 'action',
                 'data-background-image', 'data-thumb', 'data-video-src']
    
    for tag in soup.find_all(True):
        for attr in url_attrs:
            val = tag.get(attr)
            if val:
                u = normalize_url(val)
                if u:
                    urls.add(u)
        
        # srcset — может содержать несколько URL через запятую
        srcset = tag.get('srcset')
        if srcset:
            for part in srcset.split(','):
                src_url = part.strip().split()[0] if part.strip() else ''
                u = normalize_url(src_url)
                if u:
                    urls.add(u)
        
        # meta content с URL
        if tag.name == 'meta':
            content = tag.get('content', '')
            if content and ('http://' in content or 'https://' in content or '//' in content):
                # Извлекаем URL из content
                found = re.findall(r'https?://[^\s"\'<>\)\],;]+', content)
                for f in found:
                    u = normalize_url(f)
                    if u:
                        urls.add(u)
        
        # inline style с url()
        style = tag.get('style', '')
        if style and 'url(' in style:
            css_urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
            for cu in css_urls:
                u = normalize_url(cu)
                if u:
                    urls.add(u)
    
    # 2. CSS блоки <style> — url()
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            css_urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', style_tag.string)
            for cu in css_urls:
                u = normalize_url(cu)
                if u:
                    urls.add(u)
    
    # 3. Прямые URL в <script> блоках и в HTML тексте
    full_text = html_text
    direct_urls = re.findall(r'https?://[a-zA-Z0-9][^\s"\'<>\)\],;}{]+', full_text)
    for du in direct_urls:
        du = du.rstrip('.,;:!?)]\'"\\')
        u = normalize_url(du)
        if u:
            urls.add(u)
    
    # 4. Protocol-relative URL в тексте
    proto_urls = re.findall(r'//[a-zA-Z0-9][a-zA-Z0-9._-]+\.[a-zA-Z]{2,}[^\s"\'<>\)\],;}{]*', full_text)
    for pu in proto_urls:
        pu = pu.rstrip('.,;:!?)]\'"\\')
        u = normalize_url(pu)
        if u:
            urls.add(u)
    
    return list(urls)


def scan_site_sync(url, max_pages=50):
    """
    Полное сканирование сайта — находит ВСЕ домены, поддомены, CDN, ссылки.
    Парсит: теги, атрибуты, CSS url(), inline styles, srcset, meta, скрипты.
    """
    import requests
    import re
    
    if not url:
        return {'error': 'URL is required'}
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed = urlparse(url)
    main_domain = parsed.netloc
    
    if main_domain.startswith('www.'):
        base_domain = main_domain[4:]
    else:
        base_domain = main_domain
    
    # Извлекаем корневой домен
    parts = base_domain.split('.')
    if len(parts) >= 2:
        root_domain = '.'.join(parts[-2:])
    else:
        root_domain = base_domain
    
    brand_name = parts[0] if parts else base_domain
    
    domains_found = {}
    visited = set()
    to_visit = [url]
    pages_scanned = 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    def add_domain(href):
        """Добавляет домен из URL в результат"""
        try:
            link_parsed = urlparse(href)
            link_domain = link_parsed.netloc
            
            if not link_domain or '.' not in link_domain:
                return
            # Убираем порт если есть
            if ':' in link_domain:
                link_domain = link_domain.split(':')[0]
            # Пропускаем localhost/IP
            if link_domain in ('localhost', '127.0.0.1') or link_domain.startswith('192.168.'):
                return
            
            if link_domain not in domains_found:
                domains_found[link_domain] = {
                    'domain': link_domain,
                    'count': 0,
                    'is_main': link_domain == main_domain or link_domain == f'www.{base_domain}' or link_domain == base_domain,
                    'is_subdomain': link_domain.endswith(f'.{root_domain}') or link_domain == base_domain or link_domain == root_domain,
                    'is_related': root_domain in link_domain,
                    'sample_urls': []
                }
            
            domains_found[link_domain]['count'] += 1
            if len(domains_found[link_domain]['sample_urls']) < 5:
                domains_found[link_domain]['sample_urls'].append(href[:200])
            
            # Добавляем внутренние ссылки в очередь для обхода
            if link_domain == main_domain or link_domain.endswith(f'.{root_domain}'):
                clean_url = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path}"
                if clean_url not in visited and clean_url not in to_visit:
                    to_visit.append(clean_url)
        except:
            pass
    
    while to_visit and pages_scanned < max_pages:
        current_url = to_visit.pop(0)
        
        if current_url in visited:
            continue
        
        visited.add(current_url)
        pages_scanned += 1
        
        try:
            response = requests.get(current_url, headers=headers, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                continue
            
            # Полный парсинг — извлекаем ВСЕ URL из HTML
            all_urls = _extract_all_urls_from_html(response.text, current_url)
            
            for href in all_urls:
                add_domain(href)
        
        except Exception as e:
            print(f"[Analyzer] Ошибка сканирования {current_url}: {e}")
            continue
    
    # Категоризация доменов с использованием паттернов из constants
    from .constants import TRACKER_PATTERNS, CDN_PATTERNS, OPTIONAL_CDN_PATTERNS
    
    main_domains = []
    cdn_domains = []
    related_domains = []
    external_domains = []
    tracker_domains = []
    
    for domain, data in domains_found.items():
        domain_lower = domain.lower()
        
        # 1. Основной домен и поддомены
        if data['is_main'] or data['is_subdomain']:
            data['category'] = 'main'
            data['required'] = True
            data['priority'] = 'critical' if data['is_main'] else 'high'
            main_domains.append(data)
        # 2. Трекеры — НЕ скачивать
        elif any(t in domain_lower for t in TRACKER_PATTERNS):
            data['category'] = 'tracker'
            data['required'] = False
            data['priority'] = 'skip'
            tracker_domains.append(data)
        # 3. CDN
        elif any(c in domain_lower for c in CDN_PATTERNS):
            data['category'] = 'cdn'
            # Обязательный или опциональный CDN
            if any(opt in domain_lower for opt in OPTIONAL_CDN_PATTERNS):
                data['required'] = False
                data['priority'] = 'optional'
            else:
                data['required'] = True
                data['priority'] = 'high'
            cdn_domains.append(data)
        # 4. Связанные домены
        elif data['is_related']:
            data['category'] = 'related'
            data['required'] = False
            data['priority'] = 'medium'
            related_domains.append(data)
        # 5. Внешние
        else:
            data['category'] = 'external'
            data['required'] = False
            data['priority'] = 'low'
            external_domains.append(data)
    
    # Сортировка по количеству ссылок (больше → важнее)
    main_domains.sort(key=lambda x: x['count'], reverse=True)
    cdn_domains.sort(key=lambda x: x['count'], reverse=True)
    related_domains.sort(key=lambda x: x['count'], reverse=True)
    external_domains.sort(key=lambda x: x['count'], reverse=True)
    
    all_domains = main_domains + cdn_domains + related_domains + external_domains + tracker_domains
    
    return {
        'base_domain': base_domain,
        'root_domain': root_domain,
        'brand_name': brand_name,
        'pages_scanned': pages_scanned,
        'subdomains': all_domains,
        'categories': {
            'main': main_domains,
            'cdn': cdn_domains,
            'related': related_domains,
            'external': external_domains + tracker_domains
        },
        'counts': {
            'main': len(main_domains),
            'cdn': len(cdn_domains),
            'related': len(related_domains),
            'external': len(external_domains) + len(tracker_domains)
        }
    }


def start_async_scan(url, folder_name, max_pages=30):
    """Start async scan in background thread"""
    import requests
    from bs4 import BeautifulSoup
    import uuid
    
    scan_id = str(uuid.uuid4())[:8]
    
    active_scans[scan_id] = {
        'status': 'running',
        'progress': 0,
        'pages_scanned': 0,
        'folder_name': folder_name,
        'url': url,
        'result': None
    }
    
    def run_scan():
        scan = active_scans[scan_id]
        
        try:
            result = scan_site_sync(url, max_pages)
            scan['result'] = result
            scan['status'] = 'completed'
            scan['progress'] = 100
            
            # Save result to landing metadata
            if folder_name:
                meta_path = DOWNLOADS_DIR / folder_name / '_wcloner' / 'landing.json'
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r') as f:
                            meta = json.load(f)
                        meta['scan_result'] = result
                        meta['status'] = 'scanned'
                        with open(meta_path, 'w') as f:
                            json.dump(meta, f, indent=2)
                    except:
                        pass
        
        except Exception as e:
            scan['status'] = 'failed'
            scan['error'] = str(e)
    
    thread = threading.Thread(target=run_scan)
    thread.daemon = True
    thread.start()
    
    return scan_id


def get_scan_status(scan_id):
    """Get status of async scan"""
    scan = active_scans.get(scan_id)
    if not scan:
        return None
    
    return {
        'scan_id': scan_id,
        'status': scan['status'],
        'progress': scan['progress'],
        'pages_scanned': scan['pages_scanned'],
        'result': scan.get('result')
    }
