"""
Links Analyzer module - deep analysis of site links, domains and pages
Отдельный модуль для полного анализа ссылочности сайта
"""
import os
import re
import json
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import DOWNLOADS_DIR
from .constants import (
    TRACKER_PATTERNS, CDN_PATTERNS, REQUIRED_CDN_PATTERNS, OPTIONAL_CDN_PATTERNS,
    DEFAULT_HEADERS, is_valid_domain, normalize_domain, get_root_domain
)


def analyze_local_links(folder_path):
    """
    Анализ ссылок в локально скачанных HTML файлах.
    Возвращает все найденные домены, страницы и их статус.
    """
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    domains_found = {}
    pages_found = []
    local_files = set()
    
    # Собираем все локальные файлы
    for f in folder_path.rglob('*'):
        if f.is_file() and '_wcloner' not in str(f) and 'vue-app' not in str(f):
            rel_path = str(f.relative_to(folder_path))
            local_files.add(rel_path)
    
    # Анализируем HTML файлы
    html_files = list(folder_path.rglob('*.html'))
    html_files += list(folder_path.rglob('*.htm'))
    
    for html_file in html_files:
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file):
            continue
        
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Извлекаем все ссылки
            links = extract_links_from_html(content)
            
            for link in links:
                process_link(link, html_file, folder_path, domains_found, pages_found, local_files)
        
        except Exception as e:
            continue
    
    # Категоризируем домены
    categorized = categorize_domains(domains_found, folder_path.name)
    
    # Подсчёт статистики
    total_pages = len(pages_found)
    missing_pages = [p for p in pages_found if not p.get('is_downloaded')]
    
    result = {
        'total_domains': len(domains_found),
        'total_pages': total_pages,
        'missing_count': len(missing_pages),
        'categories': categorized,
        'pages': pages_found[:500],  # Лимит для производительности
        'analyzed_at': datetime.now().isoformat()
    }
    
    return result


def extract_links_from_html(content):
    """Извлекает все ссылки из HTML контента"""
    links = []
    
    # href и src атрибуты
    patterns = [
        r'href=["\']([^"\']+)["\']',
        r'src=["\']([^"\']+)["\']',
        r'data-src=["\']([^"\']+)["\']',
        r'data-href=["\']([^"\']+)["\']',
        r'data-url=["\']([^"\']+)["\']',
        r'data-image=["\']([^"\']+)["\']',
        r'data-background=["\']([^"\']+)["\']',
        r'poster=["\']([^"\']+)["\']',
        r'content=["\']([^"\']+)["\']',  # meta tags
        r'action=["\']([^"\']+)["\']',   # form action
        r'srcset=["\']([^"\']+)["\']',
        r'url\(["\']?([^"\')\s]+)["\']?\)',  # CSS url()
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        links.extend(matches)
    
    # Прямые URL в тексте и скриптах
    url_patterns = [
        r'https?://[^\s"\'<>\)\]]+',  # Прямые URL
        r'//[a-zA-Z0-9][^\s"\'<>\)\]]+',  # Protocol-relative URLs
    ]
    
    for pattern in url_patterns:
        matches = re.findall(pattern, content)
        links.extend(matches)
    
    # Обработка srcset (может содержать несколько URL)
    srcset_matches = re.findall(r'srcset=["\']([^"\']+)["\']', content, re.IGNORECASE)
    for srcset in srcset_matches:
        # srcset формат: "url1 1x, url2 2x" или "url1 100w, url2 200w"
        parts = srcset.split(',')
        for part in parts:
            url = part.strip().split()[0] if part.strip() else ''
            if url:
                links.append(url)
    
    # Очистка URL от мусора в конце
    cleaned = []
    for link in links:
        # Убираем trailing символы
        link = link.rstrip('.,;:!?)]\'"')
        if link:
            cleaned.append(link)
    
    return list(set(cleaned))


def process_link(link, html_file, folder_path, domains_found, pages_found, local_files):
    """Обрабатывает одну ссылку и добавляет в результаты"""
    
    # Пропускаем data:, javascript:, mailto:, #
    if link.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '#', '{', '$')):
        return
    
    # Определяем тип ссылки
    if link.startswith(('http://', 'https://', '//')):
        # Абсолютная ссылка
        if link.startswith('//'):
            link = 'https:' + link
        
        try:
            parsed = urlparse(link)
            domain = parsed.netloc
            
            if not domain:
                return
            
            # Валидация домена - должен содержать точку и не содержать :
            if ':' in domain or '.' not in domain:
                return
            
            # Пропускаем localhost и IP адреса
            if domain in ('localhost', '127.0.0.1') or domain.startswith('192.168.'):
                return
            
            # Добавляем домен
            if domain not in domains_found:
                domains_found[domain] = {
                    'domain': domain,
                    'count': 0,
                    'sample_urls': [],
                    'is_downloaded': check_domain_downloaded(folder_path, domain)
                }
            
            domains_found[domain]['count'] += 1
            if len(domains_found[domain]['sample_urls']) < 5:
                domains_found[domain]['sample_urls'].append(link[:200])
            
            # Добавляем страницу если это HTML
            path = parsed.path
            if path.endswith(('.html', '.htm', '/')) or '.' not in path.split('/')[-1]:
                page_info = {
                    'url': link,
                    'domain': domain,
                    'path': path or '/',
                    'is_downloaded': check_page_downloaded(folder_path, domain, path)
                }
                if page_info not in pages_found:
                    pages_found.append(page_info)
        
        except Exception:
            pass
    
    else:
        # Относительная ссылка - проверяем локальный файл
        try:
            if link.startswith('/'):
                rel_path = link[1:]
            else:
                rel_path = str((html_file.parent / link).relative_to(folder_path))
            
            # Убираем query string и fragment
            rel_path = rel_path.split('?')[0].split('#')[0]
            
            is_downloaded = rel_path in local_files
            
            if rel_path.endswith(('.html', '.htm')) or '.' not in rel_path.split('/')[-1]:
                # Определяем домен из пути
                parts = rel_path.split('/')
                domain = parts[0] if '.' in parts[0] else folder_path.name
                
                page_info = {
                    'url': f'/{rel_path}',
                    'domain': domain,
                    'path': rel_path,
                    'is_downloaded': is_downloaded
                }
                if page_info not in pages_found:
                    pages_found.append(page_info)
        
        except Exception:
            pass


def check_domain_downloaded(folder_path, domain):
    """Проверяет скачан ли домен (есть ли папка с index.html)"""
    domain_path = folder_path / domain
    if domain_path.exists():
        index_path = domain_path / 'index.html'
        return index_path.exists()
    return False


def check_page_downloaded(folder_path, domain, path):
    """Проверяет скачана ли страница"""
    if not path or path == '/':
        path = 'index.html'
    elif path.endswith('/'):
        path = path + 'index.html'
    elif '.' not in path.split('/')[-1]:
        path = path + '/index.html'
    
    # Пробуем разные варианты пути
    possible_paths = [
        folder_path / domain / path.lstrip('/'),
        folder_path / path.lstrip('/'),
        folder_path / domain / 'index.html' if path in ['/', ''] else None
    ]
    
    for p in possible_paths:
        if p and p.exists():
            return True
    
    return False


# normalize_domain и get_root_domain импортированы из constants.py


def _unused_placeholder():
    # Placeholder to maintain line structure
    pass


def categorize_domains_helper(domain):
    """Helper для категоризации"""
    parts = domain.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return domain


def categorize_domains(domains_found, main_domain):
    """Категоризирует домены по типам"""
    main = []
    cdn = []
    related = []
    external = []
    trackers = []
    
    # Нормализуем главный домен
    main_domain_normalized = normalize_domain(main_domain)
    root_domain = get_root_domain(main_domain)
    
    for domain, data in domains_found.items():
        domain_lower = domain.lower()
        domain_normalized = normalize_domain(domain)
        domain_root = get_root_domain(domain)
        
        # Категоризация
        # 1. Точное совпадение (с www или без)
        if domain_normalized == main_domain_normalized:
            data['category'] = 'main'
            data['required'] = True
            data['priority'] = 'critical'
            main.append(data)
        # 2. Тот же корневой домен (поддомены)
        elif domain_root == root_domain:
            data['category'] = 'main'
            data['required'] = True
            data['priority'] = 'high'
            main.append(data)
        # 3. Трекеры - НЕ скачивать
        elif any(t in domain_lower for t in TRACKER_PATTERNS):
            data['category'] = 'tracker'
            data['required'] = False
            data['priority'] = 'skip'
            trackers.append(data)
        # 4. CDN - проверяем обязательность
        elif any(c in domain_lower for c in CDN_PATTERNS):
            data['category'] = 'cdn'
            # Проверяем это обязательный CDN или опциональный
            if any(opt in domain_lower for opt in OPTIONAL_CDN_PATTERNS):
                data['required'] = False
                data['priority'] = 'optional'
            else:
                data['required'] = True
                data['priority'] = 'high'
            cdn.append(data)
        # 5. Внешние
        else:
            data['category'] = 'external'
            data['required'] = False
            data['priority'] = 'low'
            external.append(data)
    
    # Сортировка по количеству ссылок
    main.sort(key=lambda x: x['count'], reverse=True)
    cdn.sort(key=lambda x: x['count'], reverse=True)
    external.sort(key=lambda x: x['count'], reverse=True)
    
    return {
        'main': main,
        'cdn': cdn,
        'related': related,
        'external': external + trackers
    }


def analyze_page_deeply(url, visited=None, max_depth=2, current_depth=0):
    """
    Рекурсивно анализирует страницу и все её внутренние ссылки.
    Находит все домены на которые ссылается сайт.
    """
    import requests
    from bs4 import BeautifulSoup
    
    if visited is None:
        visited = set()
    
    domains_found = {}
    
    if current_depth > max_depth or url in visited:
        return domains_found
    
    visited.add(url)
    
    try:
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc
        
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        if response.status_code != 200:
            return domains_found
        
        content = response.text
        
        # Извлекаем все ссылки
        links = extract_links_from_html(content)
        
        internal_urls = []
        
        for link in links:
            try:
                # Нормализация
                if link.startswith('//'):
                    link = 'https:' + link
                elif link.startswith('/'):
                    link = f"{parsed_base.scheme}://{parsed_base.netloc}{link}"
                elif not link.startswith(('http://', 'https://')):
                    continue
                
                parsed = urlparse(link)
                domain = parsed.netloc
                
                if not domain or '.' not in domain:
                    continue
                if ':' in domain:
                    domain = domain.split(':')[0]
                if domain in ('localhost', '127.0.0.1'):
                    continue
                
                # Добавляем домен
                if domain not in domains_found:
                    domains_found[domain] = {
                        'domain': domain,
                        'count': 0,
                        'sample_urls': [],
                        'source': 'deep_scan'
                    }
                domains_found[domain]['count'] += 1
                if len(domains_found[domain]['sample_urls']) < 3:
                    domains_found[domain]['sample_urls'].append(link[:100])
                
                # Собираем внутренние ссылки для рекурсии
                if domain == base_domain or domain.endswith(f'.{base_domain}'):
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if clean_url not in visited:
                        internal_urls.append(clean_url)
            except:
                pass
        
        # Рекурсивно анализируем внутренние страницы (ограничиваем количество)
        for internal_url in internal_urls[:10]:
            sub_domains = analyze_page_deeply(internal_url, visited, max_depth, current_depth + 1)
            for domain, data in sub_domains.items():
                if domain not in domains_found:
                    domains_found[domain] = data
                else:
                    domains_found[domain]['count'] += data['count']
        
        return domains_found
    
    except Exception as e:
        print(f"[LinksAnalyzer] Error analyzing {url}: {e}")
        return domains_found


def parse_wget_logs(folder_path):
    """
    Парсит логи wget для поиска доменов которые были найдены но не скачаны.
    """
    folder_path = Path(folder_path)
    wcloner_dir = folder_path / '_wcloner'
    
    domains_from_logs = {}
    
    if not wcloner_dir.exists():
        return domains_from_logs
    
    # Ищем все лог файлы
    for log_file in wcloner_dir.glob('wget_*.log'):
        try:
            content = log_file.read_text(encoding='utf-8', errors='ignore')
            
            # Ищем URL которые не были скачаны
            # Паттерн: URL 'https://domain.com/...' not followed
            import re
            patterns = [
                r"URL '(https?://[^']+)' not followed",
                r"--\s+(https?://[^\s]+)\s*$",
                r"Saving to: '([^']+)'",
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    try:
                        parsed = urlparse(match)
                        domain = parsed.netloc
                        if domain and '.' in domain and ':' not in domain:
                            if domain not in domains_from_logs:
                                domains_from_logs[domain] = {
                                    'domain': domain,
                                    'count': 0,
                                    'sample_urls': [],
                                    'source': 'wget_log'
                                }
                            domains_from_logs[domain]['count'] += 1
                            if len(domains_from_logs[domain]['sample_urls']) < 3:
                                domains_from_logs[domain]['sample_urls'].append(match[:100])
                    except:
                        pass
        except:
            pass
    
    return domains_from_logs


def deep_analyze_online(url, folder_path, max_pages=50):
    """
    Глубокий онлайн анализ сайта.
    Сканирует живой сайт и сравнивает с локальной копией.
    Объединяет результаты локального, онлайн анализа и логов wget.
    """
    import requests
    from bs4 import BeautifulSoup
    
    folder_path = Path(folder_path)
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed = urlparse(url)
    main_domain = parsed.netloc
    
    # Извлекаем корневой домен
    parts = main_domain.replace('www.', '').split('.')
    if len(parts) >= 2:
        root_domain = '.'.join(parts[-2:])
    else:
        root_domain = main_domain
    
    # Сначала делаем локальный анализ
    local_result = analyze_local_links(folder_path)
    local_domains = {}
    if 'categories' in local_result:
        for cat, items in local_result.get('categories', {}).items():
            for item in items:
                domain = item.get('domain', '')
                if domain:
                    local_domains[domain] = item
                    item['source'] = 'local'  # Помечаем источник
    
    # Парсим логи wget для дополнительных доменов
    wget_log_domains = parse_wget_logs(folder_path)
    
    # Глубокий рекурсивный анализ онлайн
    print(f"[LinksAnalyzer] Running deep page analysis for {url}...")
    deep_scan_domains = analyze_page_deeply(url, max_depth=2)
    print(f"[LinksAnalyzer] Deep scan found {len(deep_scan_domains)} domains")
    
    domains_found = {}
    pages_found = []
    visited = set()
    to_visit = [url]
    pages_scanned = 0
    
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
            
            # Извлекаем ссылки из тегов
            for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'source', 'video', 'audio']):
                href = tag.get('href') or tag.get('src') or tag.get('data-src')
                if not href:
                    continue
                
                # Нормализация URL
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
                    
                    # Добавляем домен
                    if link_domain not in domains_found:
                        domains_found[link_domain] = {
                            'domain': link_domain,
                            'count': 0,
                            'sample_urls': [],
                            'is_downloaded': check_domain_downloaded(folder_path, link_domain)
                        }
                    
                    domains_found[link_domain]['count'] += 1
                    if len(domains_found[link_domain]['sample_urls']) < 3:
                        domains_found[link_domain]['sample_urls'].append(href[:100])
                    
                    # Добавляем внутренние страницы в очередь
                    if link_domain == main_domain or link_domain.endswith(f'.{root_domain}'):
                        clean_url = f"{link_parsed.scheme}://{link_parsed.netloc}{link_parsed.path}"
                        if clean_url not in visited and clean_url not in to_visit:
                            to_visit.append(clean_url)
                        
                        # Добавляем страницу
                        path = link_parsed.path or '/'
                        page_info = {
                            'url': href,
                            'domain': link_domain,
                            'path': path,
                            'is_downloaded': check_page_downloaded(folder_path, link_domain, path)
                        }
                        if not any(p['url'] == href for p in pages_found):
                            pages_found.append(page_info)
                
                except Exception:
                    continue
        
        except Exception as e:
            continue
    
    # Помечаем онлайн домены
    for domain, data in domains_found.items():
        data['source'] = 'online'
    
    # Объединяем все источники: local + wget_logs + wget2 + online
    merged_domains = {}
    
    # 1. Сначала добавляем локальные
    for domain, data in local_domains.items():
        merged_domains[domain] = data.copy()
        merged_domains[domain]['source'] = 'local'
    
    # 2. Добавляем из логов wget
    for domain, data in wget_log_domains.items():
        if domain not in merged_domains:
            merged_domains[domain] = data.copy()
            merged_domains[domain]['source'] = 'wget_log'
            merged_domains[domain]['is_downloaded'] = check_domain_downloaded(folder_path, domain)
    
    # 3. Добавляем из глубокого сканирования
    for domain, data in deep_scan_domains.items():
        if domain not in merged_domains:
            merged_domains[domain] = data.copy()
            merged_domains[domain]['source'] = 'deep_scan'
            merged_domains[domain]['is_downloaded'] = check_domain_downloaded(folder_path, domain)
        else:
            # Обновляем source если нашли и там и там
            if merged_domains[domain]['source'] == 'local':
                merged_domains[domain]['source'] = 'both'
    
    # 4. Добавляем/обновляем онлайн (BeautifulSoup)
    for domain, data in domains_found.items():
        if domain in merged_domains:
            # Домен есть и локально и онлайн
            if merged_domains[domain]['source'] in ('local', 'wget_log', 'wget2'):
                merged_domains[domain]['source'] = 'both'
            merged_domains[domain]['count'] = max(
                merged_domains[domain].get('count', 0),
                data.get('count', 0)
            )
            # Объединяем sample_urls
            existing_urls = set(merged_domains[domain].get('sample_urls', []))
            for url_sample in data.get('sample_urls', []):
                if url_sample not in existing_urls:
                    merged_domains[domain].setdefault('sample_urls', []).append(url_sample)
        else:
            # Только онлайн
            merged_domains[domain] = data.copy()
            merged_domains[domain]['source'] = 'online'
    
    # Категоризируем объединённые домены
    categorized = categorize_domains(merged_domains, main_domain)
    
    # Добавляем source в категоризированные данные
    for cat_name, cat_items in categorized.items():
        for item in cat_items:
            domain = item.get('domain', '')
            if domain in merged_domains:
                item['source'] = merged_domains[domain].get('source', 'unknown')
    
    # Подсчёт статистики
    missing_pages = [p for p in pages_found if not p.get('is_downloaded')]
    
    # Подсчёт по источникам
    local_only = sum(1 for d in merged_domains.values() if d.get('source') == 'local')
    online_only = sum(1 for d in merged_domains.values() if d.get('source') == 'online')
    deep_scan_only = sum(1 for d in merged_domains.values() if d.get('source') == 'deep_scan')
    wget_log_only = sum(1 for d in merged_domains.values() if d.get('source') == 'wget_log')
    both_sources = sum(1 for d in merged_domains.values() if d.get('source') == 'both')
    
    result = {
        'url': url,
        'base_domain': main_domain,
        'root_domain': root_domain,
        'pages_scanned': pages_scanned,
        'total_domains': len(merged_domains),
        'total_pages': len(pages_found),
        'missing_count': len(missing_pages),
        'categories': categorized,
        'pages': pages_found[:500],
        'analyzed_at': datetime.now().isoformat(),
        'source_stats': {
            'local_only': local_only,
            'online_only': online_only,
            'deep_scan': deep_scan_only,
            'wget_log': wget_log_only,
            'both': both_sources
        }
    }
    
    # Сохраняем результат в метаданные
    save_analysis_result(folder_path, result)
    
    return result


def save_analysis_result(folder_path, result):
    """Сохраняет результат анализа в метаданные"""
    folder_path = Path(folder_path)
    meta_dir = folder_path / '_wcloner'
    meta_dir.mkdir(exist_ok=True)
    
    analysis_file = meta_dir / 'links_analysis.json'
    
    try:
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[LinksAnalyzer] Error saving analysis: {e}")


def load_analysis_result(folder_path):
    """Загружает сохранённый результат анализа"""
    folder_path = Path(folder_path)
    analysis_file = folder_path / '_wcloner' / 'links_analysis.json'
    
    if not analysis_file.exists():
        return None
    
    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def get_links_analysis(folder_name):
    """
    Получает анализ ссылок для папки.
    Сначала пробует загрузить сохранённый, если нет - делает локальный анализ.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    # Пробуем загрузить сохранённый анализ
    saved = load_analysis_result(folder_path)
    if saved:
        return saved
    
    # Делаем локальный анализ
    return analyze_local_links(folder_path)


def run_deep_analysis(folder_name, url=None, max_pages=50):
    """
    Запускает глубокий онлайн анализ.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        return {'error': 'Folder not found'}
    
    if not url:
        # Пробуем получить URL из метаданных
        meta_path = folder_path / '_wcloner' / 'landing.json'
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
                url = meta.get('url', f'https://{folder_name}')
            except:
                url = f'https://{folder_name}'
        else:
            url = f'https://{folder_name}'
    
    return deep_analyze_online(url, folder_path, max_pages)
