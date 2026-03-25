"""
Page Checker - система проверки страниц на 404 и анализ причин ошибок
Проверяет локальные ссылки, находит битые, анализирует причины и предлагает решения
"""
import os
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import DOWNLOADS_DIR
from .constants import (
    STATUS_DESCRIPTIONS, ERROR_REASONS, DEFAULT_HEADERS, 
    DEFAULT_TIMEOUT, get_file_type
)


def check_url_status(url, timeout=10):
    """
    Проверяет статус URL онлайн.
    Возвращает статус код, финальный URL (после редиректов), и время ответа.
    """
    import requests
    
    try:
        start_time = datetime.now()
        response = requests.head(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Если HEAD не работает, пробуем GET
        if response.status_code >= 400:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True, stream=True)
            response.close()
        
        return {
            'status_code': response.status_code,
            'final_url': response.url,
            'redirected': response.url != url,
            'elapsed': round(elapsed, 2),
            'headers': dict(response.headers)
        }
    
    except requests.exceptions.Timeout:
        return {
            'status_code': 0,
            'error': 'timeout',
            'reason': ERROR_REASONS['timeout']
        }
    except requests.exceptions.ConnectionError:
        return {
            'status_code': 0,
            'error': 'connection_error',
            'reason': 'Ошибка соединения'
        }
    except Exception as e:
        return {
            'status_code': 0,
            'error': str(e),
            'reason': ERROR_REASONS['unknown']
        }


def analyze_error_reason(url, status_code, response_data, folder_path):
    """
    Анализирует причину ошибки и предлагает решение.
    """
    reason = {
        'code': 'unknown',
        'description': ERROR_REASONS['unknown'],
        'suggestion': None,
        'can_fix': False
    }
    
    if status_code == 404:
        # Проверяем есть ли редирект
        if response_data.get('redirected'):
            reason['code'] = 'moved'
            reason['description'] = f"Страница перемещена на {response_data.get('final_url')}"
            reason['suggestion'] = 'Скачать страницу по новому URL'
            reason['can_fix'] = True
            reason['fix_url'] = response_data.get('final_url')
        else:
            # Проверяем похожие страницы
            similar = find_similar_pages(url, folder_path)
            if similar:
                reason['code'] = 'typo'
                reason['description'] = 'Возможно опечатка в URL'
                reason['suggestion'] = f"Похожие страницы: {', '.join(similar[:3])}"
                reason['similar_pages'] = similar
            else:
                reason['code'] = 'deleted'
                reason['description'] = ERROR_REASONS['deleted']
                reason['suggestion'] = 'Страница больше не существует'
    
    elif status_code == 301 or status_code == 302:
        reason['code'] = 'moved'
        reason['description'] = f"Редирект на {response_data.get('final_url')}"
        reason['suggestion'] = 'Обновить ссылку или скачать по новому URL'
        reason['can_fix'] = True
        reason['fix_url'] = response_data.get('final_url')
    
    elif status_code == 403:
        reason['code'] = 'protected'
        reason['description'] = ERROR_REASONS['protected']
        reason['suggestion'] = 'Требуется авторизация или VPN'
    
    elif status_code == 410:
        reason['code'] = 'deleted'
        reason['description'] = 'Страница намеренно удалена (Gone)'
        reason['suggestion'] = 'Страница больше не будет доступна'
    
    elif status_code >= 500:
        reason['code'] = 'server_error'
        reason['description'] = f"Ошибка сервера ({status_code})"
        reason['suggestion'] = 'Попробуйте позже'
        reason['can_fix'] = True
    
    return reason


def find_similar_pages(url, folder_path):
    """
    Ищет похожие страницы в локальной копии.
    """
    folder_path = Path(folder_path)
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if not path:
        return []
    
    # Извлекаем имя файла без расширения
    filename = path.split('/')[-1]
    name_parts = re.split(r'[-_.]', filename.lower())
    
    similar = []
    
    # Ищем файлы с похожими именами
    for html_file in folder_path.rglob('*.html'):
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file):
            continue
        
        file_name = html_file.stem.lower()
        file_parts = re.split(r'[-_.]', file_name)
        
        # Считаем совпадающие части
        common = set(name_parts) & set(file_parts)
        if len(common) >= 1 and len(common) / max(len(name_parts), 1) > 0.3:
            rel_path = str(html_file.relative_to(folder_path))
            similar.append(rel_path)
    
    return similar[:10]


def check_local_links(folder_path, max_pages=100):
    """
    Проверяет все локальные ссылки в HTML файлах.
    Находит битые ссылки (файлы которых нет локально).
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    broken_links = []
    checked_links = set()
    pages_checked = 0
    
    # Паттерны для извлечения ссылок
    link_patterns = [
        r'href=["\']([^"\'#]+)["\']',
        r'src=["\']([^"\']+)["\']'
    ]
    
    html_files = list(folder_path.rglob('*.html'))
    
    for html_file in html_files[:max_pages]:
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file) or 'node_modules' in str(html_file):
            continue
        
        pages_checked += 1
        
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for pattern in link_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                for link in matches:
                    # Пропускаем внешние, data:, javascript:
                    if link.startswith(('http://', 'https://', 'data:', 'javascript:', 'mailto:', 'tel:', '//')):
                        continue
                    
                    # Пропускаем якоря
                    if link.startswith('#'):
                        continue
                    
                    # Нормализуем путь
                    if link.startswith('/'):
                        local_path = folder_path / link.lstrip('/')
                    else:
                        local_path = html_file.parent / link
                    
                    # Убираем query string
                    local_path = Path(str(local_path).split('?')[0].split('#')[0])
                    
                    # Проверяем уникальность
                    link_key = str(local_path)
                    if link_key in checked_links:
                        continue
                    checked_links.add(link_key)
                    
                    # Проверяем существование файла
                    if not local_path.exists():
                        # Проверяем с index.html
                        if not (local_path / 'index.html').exists():
                            broken_links.append({
                                'link': link,
                                'expected_path': str(local_path.relative_to(folder_path)) if local_path.is_relative_to(folder_path) else str(local_path),
                                'referenced_from': str(html_file.relative_to(folder_path)),
                                'type': get_link_type(link)
                            })
        
        except Exception as e:
            continue
    
    # Группируем по типу
    by_type = {}
    for bl in broken_links:
        t = bl['type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(bl)
    
    return {
        'total_broken': len(broken_links),
        'pages_checked': pages_checked,
        'by_type': by_type,
        'broken_links': broken_links[:200],  # Лимит
        'checked_at': datetime.now().isoformat()
    }


def get_link_type(link):
    """Определяет тип ссылки по расширению"""
    link_lower = link.lower()
    
    if any(link_lower.endswith(ext) for ext in ['.html', '.htm', '.php', '/']):
        return 'page'
    elif any(link_lower.endswith(ext) for ext in ['.js']):
        return 'script'
    elif any(link_lower.endswith(ext) for ext in ['.css']):
        return 'style'
    elif any(link_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']):
        return 'image'
    elif any(link_lower.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
        return 'font'
    elif any(link_lower.endswith(ext) for ext in ['.mp4', '.webm', '.mp3', '.ogg']):
        return 'media'
    elif any(link_lower.endswith(ext) for ext in ['.json', '.xml']):
        return 'data'
    else:
        return 'other'


def check_pages_online(urls, folder_path, max_concurrent=5):
    """
    Проверяет список URL онлайн параллельно.
    Возвращает статус каждой страницы и анализ ошибок.
    """
    folder_path = Path(folder_path)
    results = []
    
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(check_url_status, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                response_data = future.result()
                status_code = response_data.get('status_code', 0)
                
                result = {
                    'url': url,
                    'status_code': status_code,
                    'status_text': STATUS_DESCRIPTIONS.get(status_code, 'Unknown'),
                    'is_ok': 200 <= status_code < 400,
                    'is_error': status_code >= 400 or status_code == 0,
                    'elapsed': response_data.get('elapsed'),
                    'redirected': response_data.get('redirected', False),
                    'final_url': response_data.get('final_url')
                }
                
                # Анализируем ошибки
                if result['is_error']:
                    result['reason'] = analyze_error_reason(url, status_code, response_data, folder_path)
                
                results.append(result)
            
            except Exception as e:
                results.append({
                    'url': url,
                    'status_code': 0,
                    'status_text': 'Error',
                    'is_ok': False,
                    'is_error': True,
                    'error': str(e),
                    'reason': {
                        'code': 'unknown',
                        'description': str(e)
                    }
                })
    
    # Статистика
    ok_count = sum(1 for r in results if r['is_ok'])
    error_count = sum(1 for r in results if r['is_error'])
    redirect_count = sum(1 for r in results if r.get('redirected'))
    
    return {
        'total': len(results),
        'ok': ok_count,
        'errors': error_count,
        'redirects': redirect_count,
        'results': results,
        'checked_at': datetime.now().isoformat()
    }


def check_all_internal_links(folder_path, base_url=None, max_pages=50):
    """
    Полная проверка: находит все внутренние ссылки и проверяет их онлайн.
    """
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    # Определяем base_url
    if not base_url:
        meta_path = folder_path / '_wcloner' / 'landing.json'
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            base_url = meta.get('url', f'https://{folder_path.name}')
        else:
            base_url = f'https://{folder_path.name}'
    
    parsed_base = urlparse(base_url)
    main_domain = parsed_base.netloc
    
    # Собираем все внутренние ссылки
    internal_urls = set()
    
    html_files = list(folder_path.rglob('*.html'))[:max_pages]
    
    for html_file in html_files:
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file):
            continue
        
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Извлекаем href
            hrefs = re.findall(r'href=["\']([^"\'#]+)["\']', content, re.IGNORECASE)
            
            for href in hrefs:
                # Абсолютные URL того же домена
                if href.startswith(('http://', 'https://')):
                    parsed = urlparse(href)
                    if parsed.netloc == main_domain or parsed.netloc == f'www.{main_domain}':
                        internal_urls.add(href)
                
                # Относительные URL
                elif not href.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '//')):
                    if href.startswith('/'):
                        full_url = f"{parsed_base.scheme}://{main_domain}{href}"
                    else:
                        # Относительно текущего файла
                        rel_path = html_file.relative_to(folder_path)
                        parent_path = str(rel_path.parent).replace('\\', '/')
                        if parent_path == '.':
                            full_url = f"{parsed_base.scheme}://{main_domain}/{href}"
                        else:
                            full_url = f"{parsed_base.scheme}://{main_domain}/{parent_path}/{href}"
                    
                    internal_urls.add(full_url)
        
        except Exception:
            continue
    
    # Ограничиваем количество для проверки
    urls_to_check = list(internal_urls)[:100]
    
    # Проверяем онлайн
    check_results = check_pages_online(urls_to_check, folder_path)
    
    return {
        'base_url': base_url,
        'total_internal_links': len(internal_urls),
        'checked': len(urls_to_check),
        **check_results
    }


def download_working_pages(folder_path, check_results, max_download=20):
    """
    Докачивает страницы которые работают онлайн но отсутствуют локально.
    """
    import requests
    
    folder_path = Path(folder_path)
    downloaded = []
    failed = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # Находим страницы для докачки
    to_download = []
    
    for result in check_results.get('results', []):
        if not result.get('is_ok'):
            continue
        
        url = result.get('final_url') or result.get('url')
        parsed = urlparse(url)
        
        # Определяем локальный путь
        domain = parsed.netloc
        path = parsed.path.strip('/') or 'index.html'
        
        if not path.endswith(('.html', '.htm')):
            if '.' not in path.split('/')[-1]:
                path = path.rstrip('/') + '/index.html'
        
        local_path = folder_path / domain / path
        
        # Проверяем существует ли локально
        if not local_path.exists():
            to_download.append({
                'url': url,
                'local_path': local_path,
                'rel_path': str(local_path.relative_to(folder_path))
            })
    
    # Скачиваем
    for item in to_download[:max_download]:
        try:
            response = requests.get(item['url'], headers=headers, timeout=15)
            
            if response.status_code == 200:
                item['local_path'].parent.mkdir(parents=True, exist_ok=True)
                with open(item['local_path'], 'wb') as f:
                    f.write(response.content)
                
                downloaded.append({
                    'url': item['url'],
                    'path': item['rel_path'],
                    'size': len(response.content)
                })
            else:
                failed.append({
                    'url': item['url'],
                    'error': f'HTTP {response.status_code}'
                })
        
        except Exception as e:
            failed.append({
                'url': item['url'],
                'error': str(e)
            })
    
    return {
        'total_to_download': len(to_download),
        'downloaded': len(downloaded),
        'failed': len(failed),
        'downloaded_files': downloaded,
        'failed_files': failed
    }


def fix_broken_links(folder_path, check_results):
    """
    Пытается исправить битые ссылки:
    - Скачивает страницы по новым URL (редиректы)
    - Обновляет ссылки в HTML если страница перемещена
    """
    folder_path = Path(folder_path)
    fixes = []
    
    for result in check_results.get('results', []):
        reason = result.get('reason', {})
        
        if reason.get('can_fix') and reason.get('fix_url'):
            fix_url = reason['fix_url']
            original_url = result['url']
            
            # Скачиваем по новому URL
            download_result = download_single_page(fix_url, folder_path)
            
            if download_result.get('success'):
                fixes.append({
                    'original_url': original_url,
                    'fixed_url': fix_url,
                    'action': 'downloaded',
                    'path': download_result.get('path')
                })
    
    return {
        'total_fixes': len(fixes),
        'fixes': fixes
    }


def download_single_page(url, folder_path):
    """Скачивает одну страницу"""
    import requests
    
    folder_path = Path(folder_path)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            parsed = urlparse(response.url)
            domain = parsed.netloc
            path = parsed.path.strip('/') or 'index.html'
            
            if not path.endswith(('.html', '.htm')):
                if '.' not in path.split('/')[-1]:
                    path = path.rstrip('/') + '/index.html'
            
            local_path = folder_path / domain / path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            
            return {
                'success': True,
                'path': str(local_path.relative_to(folder_path)),
                'size': len(response.content)
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}'
            }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def get_page_check_summary(folder_path):
    """
    Возвращает краткую сводку по проверке страниц.
    """
    folder_path = Path(folder_path)
    
    # Проверяем локальные ссылки
    local_check = check_local_links(folder_path, max_pages=50)
    
    return {
        'broken_links': local_check.get('total_broken', 0),
        'pages_checked': local_check.get('pages_checked', 0),
        'by_type': local_check.get('by_type', {}),
        'top_broken': local_check.get('broken_links', [])[:10]
    }
