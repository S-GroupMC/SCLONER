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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
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


def scan_site_sync(url, max_pages=50):
    """Synchronous site scan - find all subdomains and create a link map"""
    import requests
    from bs4 import BeautifulSoup
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
    
    # Extract root domain
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
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
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
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'source', 'video', 'audio']):
                href = tag.get('href') or tag.get('src') or tag.get('data-src')
                if not href:
                    continue
                
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
                    
                    if link_domain not in domains_found:
                        domains_found[link_domain] = {
                            'domain': link_domain,
                            'count': 0,
                            'is_main': link_domain == main_domain or link_domain == f'www.{base_domain}',
                            'is_subdomain': link_domain.endswith(f'.{base_domain}') or link_domain == base_domain,
                            'is_related': root_domain in link_domain,
                            'sample_urls': []
                        }
                    
                    domains_found[link_domain]['count'] += 1
                    if len(domains_found[link_domain]['sample_urls']) < 3:
                        domains_found[link_domain]['sample_urls'].append(href[:100])
                    
                    # Add internal links to visit queue
                    if (link_domain == main_domain or link_domain.endswith(f'.{base_domain}')):
                        clean_url = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path}"
                        if clean_url not in visited and clean_url not in to_visit:
                            to_visit.append(clean_url)
                
                except:
                    continue
        
        except Exception as e:
            continue
    
    # Categorize domains
    main_domains = []
    related_domains = set()
    cdn_domains = set()
    external_domains = set()
    
    cdn_patterns = ['cdn', 'static', 'assets', 'images', 'img', 'media', 'fonts', 'cloudfront', 'cloudflare', 'akamai', 'fastly']
    
    for domain, data in domains_found.items():
        if data['is_main'] or data['is_subdomain']:
            main_domains.append(data)
        elif data['is_related']:
            related_domains.add(domain)
        elif any(p in domain.lower() for p in cdn_patterns):
            cdn_domains.add(domain)
        else:
            external_domains.add(domain)
    
    def to_list(domain_set, category):
        return [{'domain': d, 'category': category, 'count': domains_found.get(d, {}).get('count', 0)} for d in domain_set]
    
    related_list = to_list(related_domains, 'related')
    cdn_list = to_list(cdn_domains, 'cdn')
    external_list = to_list(external_domains, 'external')
    
    all_domains = main_domains + related_list + cdn_list + external_list
    
    return {
        'base_domain': base_domain,
        'root_domain': root_domain,
        'brand_name': brand_name,
        'pages_scanned': pages_scanned,
        'subdomains': all_domains,
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
