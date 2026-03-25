"""
Dynamic Downloader - механизм докачки динамически загружаемых ресурсов
Использует Puppeteer для мониторинга сетевых запросов при просмотре страницы
"""
import os
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

from .config import DOWNLOADS_DIR
from .constants import TRACKER_PATTERNS, DOWNLOAD_EXTENSIONS, DEFAULT_HEADERS


def should_download(url):
    """Проверяет нужно ли скачивать этот URL"""
    url_lower = url.lower()
    
    # Игнорируем трекеры
    for pattern in TRACKER_PATTERNS:
        if pattern in url_lower:
            return False
    
    # Игнорируем data: и blob: URL
    if url.startswith(('data:', 'blob:', 'javascript:', 'about:')):
        return False
    
    return True


def get_local_path(url, folder_path, main_domain):
    """Определяет локальный путь для URL"""
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.lstrip('/') or 'index.html'
    
    # Добавляем query string к имени файла если есть
    if parsed.query:
        # Хэшируем query для уникальности
        import hashlib
        query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
        base, ext = os.path.splitext(path)
        if ext:
            path = f"{base}_{query_hash}{ext}"
        else:
            path = f"{path}_{query_hash}"
    
    # Если путь заканчивается на / - добавляем index.html
    if path.endswith('/'):
        path += 'index.html'
    
    # Если нет расширения - добавляем .html для HTML контента
    if '.' not in os.path.basename(path):
        path += '/index.html'
    
    return folder_path / domain / path


async def capture_network_requests_puppeteer(url, folder_path, timeout=30, scroll=True):
    """
    Открывает страницу в Puppeteer и перехватывает все сетевые запросы.
    Возвращает список URL которые нужно докачать.
    """
    folder_path = Path(folder_path)
    
    # Node.js скрипт для Puppeteer
    script = f'''
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }});
    
    const page = await browser.newPage();
    
    // Собираем все сетевые запросы
    const requests = new Set();
    
    page.on('request', request => {{
        const url = request.url();
        if (url.startsWith('http')) {{
            requests.add(url);
        }}
    }});
    
    page.on('response', response => {{
        const url = response.url();
        if (url.startsWith('http')) {{
            requests.add(url);
        }}
    }});
    
    try {{
        await page.goto('{url}', {{
            waitUntil: 'networkidle2',
            timeout: {timeout * 1000}
        }});
        
        // Скроллим страницу для lazy loading
        {'await autoScroll(page);' if scroll else ''}
        
        // Ждём ещё немного для догрузки
        await new Promise(r => setTimeout(r, 2000));
        
    }} catch (e) {{
        console.error('Navigation error:', e.message);
    }}
    
    await browser.close();
    
    // Выводим JSON с запросами
    console.log(JSON.stringify(Array.from(requests)));
}})();

async function autoScroll(page) {{
    await page.evaluate(async () => {{
        await new Promise((resolve) => {{
            let totalHeight = 0;
            const distance = 300;
            const timer = setInterval(() => {{
                const scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                
                if (totalHeight >= scrollHeight) {{
                    clearInterval(timer);
                    resolve();
                }}
            }}, 100);
        }});
    }});
}}
'''
    
    # Сохраняем скрипт во временный файл
    script_path = folder_path / '_wcloner' / 'capture_requests.js'
    script_path.parent.mkdir(exist_ok=True)
    
    with open(script_path, 'w') as f:
        f.write(script)
    
    try:
        # Запускаем Node.js
        result = subprocess.run(
            ['node', str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
            cwd=str(folder_path)
        )
        
        if result.returncode == 0:
            # Парсим JSON из stdout
            output = result.stdout.strip()
            # Находим JSON в выводе
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('['):
                    return json.loads(line)
        
        return []
    
    except subprocess.TimeoutExpired:
        return []
    except Exception as e:
        print(f"[DynamicDownloader] Error: {e}")
        return []


def download_captured_resources(urls, folder_path, main_domain):
    """
    Скачивает перехваченные ресурсы которых нет локально.
    """
    import requests
    
    folder_path = Path(folder_path)
    results = {
        'total': 0,
        'downloaded': 0,
        'skipped': 0,
        'failed': 0,
        'files': []
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    for url in urls:
        if not should_download(url):
            continue
        
        results['total'] += 1
        
        local_path = get_local_path(url, folder_path, main_domain)
        
        # Пропускаем если файл уже существует
        if local_path.exists():
            results['skipped'] += 1
            continue
        
        try:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if response.status_code == 200 and len(response.content) > 0:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                results['downloaded'] += 1
                results['files'].append({
                    'url': url,
                    'path': str(local_path.relative_to(folder_path)),
                    'size': len(response.content)
                })
            else:
                results['failed'] += 1
        
        except Exception as e:
            results['failed'] += 1
    
    return results


def scan_page_for_missing(url, folder_path, timeout=30):
    """
    Сканирует страницу и докачивает недостающие ресурсы.
    Синхронная обёртка для async функции.
    """
    folder_path = Path(folder_path)
    
    parsed = urlparse(url)
    main_domain = parsed.netloc
    
    # Запускаем async функцию
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        captured_urls = loop.run_until_complete(
            capture_network_requests_puppeteer(url, folder_path, timeout)
        )
    finally:
        loop.close()
    
    if not captured_urls:
        return {
            'status': 'no_requests',
            'message': 'No network requests captured',
            'url': url
        }
    
    # Скачиваем недостающие
    results = download_captured_resources(captured_urls, folder_path, main_domain)
    results['url'] = url
    results['captured_total'] = len(captured_urls)
    results['scanned_at'] = datetime.now().isoformat()
    
    return results


def scan_multiple_pages(urls, folder_path, timeout=30):
    """
    Сканирует несколько страниц и докачивает недостающие ресурсы.
    """
    folder_path = Path(folder_path)
    
    all_results = {
        'pages_scanned': 0,
        'total_downloaded': 0,
        'total_skipped': 0,
        'total_failed': 0,
        'pages': []
    }
    
    for url in urls:
        result = scan_page_for_missing(url, folder_path, timeout)
        all_results['pages_scanned'] += 1
        all_results['total_downloaded'] += result.get('downloaded', 0)
        all_results['total_skipped'] += result.get('skipped', 0)
        all_results['total_failed'] += result.get('failed', 0)
        all_results['pages'].append({
            'url': url,
            'downloaded': result.get('downloaded', 0),
            'captured': result.get('captured_total', 0)
        })
    
    all_results['scanned_at'] = datetime.now().isoformat()
    return all_results


def quick_scan_missing_resources(folder_path):
    """
    Быстрое сканирование HTML файлов на предмет недостающих ресурсов.
    Без Puppeteer - просто парсинг HTML.
    """
    import re
    
    folder_path = Path(folder_path)
    missing = []
    
    # Паттерны для извлечения URL
    patterns = [
        r'src=["\']([^"\']+)["\']',
        r'href=["\']([^"\']+\.(?:css|js|woff2?|ttf|eot|otf))["\']',
        r'url\(["\']?([^"\')\s]+)["\']?\)',
        r'srcset=["\']([^"\']+)["\']'
    ]
    
    html_files = list(folder_path.rglob('*.html'))
    
    for html_file in html_files:
        if '_wcloner' in str(html_file) or 'vue-app' in str(html_file) or 'node_modules' in str(html_file):
            continue
        
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Обработка srcset
                    if ',' in match and ' ' in match:
                        for part in match.split(','):
                            url = part.strip().split()[0]
                            if url:
                                check_and_add_missing(url, html_file, folder_path, missing)
                    else:
                        check_and_add_missing(match, html_file, folder_path, missing)
        
        except Exception:
            continue
    
    return {
        'total_missing': len(missing),
        'missing': missing[:200]  # Лимит
    }


def check_and_add_missing(url, html_file, folder_path, missing):
    """Проверяет существует ли ресурс локально"""
    # Пропускаем внешние URL, data:, etc
    if url.startswith(('http://', 'https://', 'data:', '//', 'javascript:', '#')):
        return
    
    # Пропускаем если уже в списке
    if any(m['url'] == url for m in missing):
        return
    
    # Определяем локальный путь
    if url.startswith('/'):
        local_path = folder_path / url.lstrip('/')
    else:
        local_path = html_file.parent / url
    
    # Убираем query string
    local_path = Path(str(local_path).split('?')[0].split('#')[0])
    
    if not local_path.exists():
        missing.append({
            'url': url,
            'expected_path': str(local_path.relative_to(folder_path)) if local_path.is_relative_to(folder_path) else str(local_path),
            'referenced_from': str(html_file.relative_to(folder_path))
        })
