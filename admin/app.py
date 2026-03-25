#!/usr/bin/env python3
"""
Wget Web Admin - Web interface for GNU Wget (FastAPI version)
Refactored: all logic moved to modules/
"""

import os
import json
import shutil
import signal
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import socketio

# Import modules
from modules.config import (
    BASE_DIR, DOWNLOADS_DIR, WGET2_PATH, PREVIEWS_DIR,
    jobs, save_jobs, load_jobs, active_scans,
    load_landings_config, save_landings_config, running_servers
)
from modules.utils import (
    extract_domain_from_url, normalize_url, format_size, find_index_file
)
from modules.downloader import (
    WgetJob, build_wget_command, build_httrack_command, build_puppeteer_command,
    run_wget_job, start_job_thread, start_job_process, get_domain_filter_config
)
from modules.analyzer import (
    check_site_changes, check_page_changes, check_all_pages_changes,
    check_site_integrity, scan_site_sync, start_async_scan, get_scan_status
)
from modules.file_manager import (
    download_missing_files, generate_preview_screenshot, generate_vue_wrapper,
    generate_server_files, prepare_landing_folder, get_folder_stats
)
from modules.server_manager import (
    get_domain_ports, find_free_port, is_port_in_use, check_process_running,
    get_servers_status, start_vue_server, start_backend_server, stop_servers, stop_vue_server,
    kill_registered_servers
)
from modules.links_analyzer import (
    get_links_analysis, run_deep_analysis
)
from modules.dynamic_downloader import (
    scan_page_for_missing, scan_multiple_pages, quick_scan_missing_resources
)
from modules.page_checker import (
    check_local_links, check_pages_online, check_all_internal_links,
    download_working_pages, fix_broken_links, get_page_check_summary
)

# FastAPI app
app = FastAPI(title="Wget Web Admin", version="2.0")


@app.on_event("startup")
async def startup_event():
    """Load jobs on startup (needed for uvicorn --reload)."""
    print(f"[WCLoner] Starting up...")
    print(f"[WCLoner] Using wget2: {WGET2_PATH}")
    print(f"[WCLoner] Downloads dir: {DOWNLOADS_DIR}")
    load_jobs()
    kill_registered_servers()

# Socket.IO for WebSocket support
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)


# =============================================================================
# API ENDPOINTS - Jobs
# =============================================================================

@app.get('/api/jobs')
async def get_jobs():
    return [job.to_dict() for job in jobs.values()]


@app.post('/api/jobs')
async def create_job(request: Request):
    data = await request.json()
    url = data.get('url', '').strip()
    
    if not url:
        raise HTTPException(status_code=400, detail={'error': 'URL is required'})
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    normalized_url = normalize_url(url)
    for job in jobs.values():
        if normalize_url(job.url) == normalized_url and job.status == 'running':
            raise HTTPException(status_code=400, detail={'error': 'Job already running for this URL'})
    
    options = data.get('options', {})
    use_wget2 = data.get('use_wget2', True)
    engine = data.get('engine', 'wget2')
    folder_name = data.get('folder_name', '')
    
    if not folder_name:
        domain = extract_domain_from_url(url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{domain}_{timestamp}"
    
    job_id = str(uuid.uuid4())[:8]
    job = WgetJob(job_id, url, options, use_wget2, folder_name, engine)
    jobs[job_id] = job
    save_jobs()
    
    start_job_process(job_id)
    return job.to_dict()


@app.get('/api/jobs/{job_id}')
async def get_job(job_id):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    return job.to_dict()


@app.delete('/api/jobs/{job_id}')
async def delete_job(job_id):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    
    if job.process and job.process.poll() is None:
        job.process.terminate()
    
    del jobs[job_id]
    save_jobs()
    return {'success': True}


@app.post('/api/jobs/{job_id}/stop')
async def stop_job(job_id):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    
    job.stop_requested = True
    
    # Try to terminate the process
    if job.process and job.process.poll() is None:
        try:
            # Kill the entire process group
            import os
            import signal
            os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
        except:
            try:
                job.process.terminate()
            except:
                pass
        job.output_lines.append("[Process] Stopped by user")
    
    # Always mark as stopped if status is running/pending
    if job.status in ['running', 'pending']:
        job.status = 'stopped'
        job.finished_at = datetime.now()
        save_jobs()
    
    return job.to_dict()


@app.post('/api/jobs/{job_id}/pause')
async def pause_job(job_id):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    
    if job.process and job.process.poll() is None and job.status == 'running':
        job.process.send_signal(signal.SIGSTOP)
        job.status = 'paused'
        save_jobs()
    
    return job.to_dict()


@app.post('/api/jobs/{job_id}/resume')
async def resume_job(job_id):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    
    if job.process and job.process.poll() is None and job.status == 'paused':
        job.process.send_signal(signal.SIGCONT)
        job.status = 'running'
        save_jobs()
    
    return job.to_dict()


@app.post('/api/jobs/{job_id}/restart')
async def restart_job(job_id, request: Request):
    data = await request.json() if request else {}
    old_job = jobs.get(job_id)
    if not old_job:
        raise HTTPException(status_code=404, detail={'error': 'Job not found'})
    
    if old_job.process and old_job.process.poll() is None:
        old_job.process.terminate()
    
    engine = data.get('engine', old_job.engine)
    use_wget2 = data.get('use_wget2', old_job.use_wget2)
    
    new_options = old_job.options.copy()
    if data.get('extra_domains'):
        new_options['extra_domains'] = data['extra_domains']
        new_options['include_subdomains'] = True
    
    new_job_id = str(uuid.uuid4())[:8]
    new_job = WgetJob(new_job_id, old_job.url, new_options, use_wget2, old_job.folder_name, engine)
    jobs[new_job_id] = new_job
    save_jobs()
    
    start_job_thread(new_job_id)
    return new_job.to_dict()


# =============================================================================
# API ENDPOINTS - Downloads
# =============================================================================

@app.get('/api/downloads')
async def list_downloads():
    downloads = []
    
    if not DOWNLOADS_DIR.exists():
        return downloads
    
    for folder in DOWNLOADS_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        if folder.name.startswith('.'):
            continue
        
        stats = get_folder_stats(folder)
        if not stats:
            continue
        
        # Check for landing metadata
        meta_path = folder / '_wcloner' / 'landing.json'
        landing_meta = None
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    landing_meta = json.load(f)
            except:
                pass
        
        # Get modification time
        try:
            mtime = folder.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        except:
            date_str = ''
        
        # Determine status
        status = 'unknown'
        is_active = False
        
        if landing_meta:
            status = landing_meta.get('status', 'prepared')
            job_id = landing_meta.get('download_job_id')
            if job_id and job_id in jobs:
                job = jobs[job_id]
                status = job.status
                is_active = job.status == 'running'
        
        downloads.append({
            'name': folder.name,
            'path': str(folder),
            'files': stats['total_files'],
            'size': stats['total_size_formatted'],
            'date': date_str,
            'status': status,
            'is_active': is_active,
            'landing_meta': landing_meta
        })
    
    downloads.sort(key=lambda x: x['date'], reverse=True)
    return downloads


@app.get('/api/landings')
async def get_landings():
    """Get landings grouped by parent domain"""
    if not DOWNLOADS_DIR.exists():
        return []
    
    domains_map = {}
    
    for folder in DOWNLOADS_DIR.iterdir():
        if not folder.is_dir() or folder.name.startswith('.'):
            continue
        
        stats = get_folder_stats(folder)
        if not stats:
            continue
        
        # Get landing metadata
        meta_path = folder / '_wcloner' / 'landing.json'
        landing_meta = None
        if meta_path.exists():
            try:
                with open(meta_path, 'r') as f:
                    landing_meta = json.load(f)
            except:
                pass
        
        # Get modification time
        try:
            mtime = folder.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        except:
            date_str = ''
        
        # Extract parent domain
        domain = landing_meta.get('domain', folder.name) if landing_meta else folder.name
        parts = domain.split('.')
        if len(parts) >= 2:
            parent_domain = '.'.join(parts[-2:])
        else:
            parent_domain = domain
        
        # Determine status
        status = 'unknown'
        if landing_meta:
            status = landing_meta.get('status', 'prepared')
            job_id = landing_meta.get('download_job_id')
            if job_id and job_id in jobs:
                job = jobs[job_id]
                status = job.status
        
        folder_data = {
            'folder_name': folder.name,
            'domain': domain,
            'path': str(folder),
            'files': stats['total_files'],
            'size': stats['total_size_formatted'],
            'total_size': stats['total_size'],
            'date': date_str,
            'status': status,
            'landing_meta': landing_meta
        }
        
        if parent_domain not in domains_map:
            domains_map[parent_domain] = {
                'parent_domain': parent_domain,
                'folders': [],
                'total_size': 0
            }
        
        domains_map[parent_domain]['folders'].append(folder_data)
        domains_map[parent_domain]['total_size'] += stats['total_size']
    
    # Convert to list and format
    result = []
    for pd, data in domains_map.items():
        data['total_size_formatted'] = format_size(data['total_size'])
        data['folders'].sort(key=lambda x: x['date'], reverse=True)
        result.append(data)
    
    result.sort(key=lambda x: x['parent_domain'])
    return result


@app.get('/api/downloads/{folder_name}')
async def get_download_details(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    stats = get_folder_stats(folder_path)
    
    # Get landing metadata
    meta_path = folder_path / '_wcloner' / 'landing.json'
    landing_meta = None
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                landing_meta = json.load(f)
        except:
            pass
    
    return {
        'name': folder_name,
        'path': str(folder_path),
        'stats': stats,
        'landing_meta': landing_meta
    }


@app.delete('/api/downloads/{folder_name}')
async def delete_download(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    try:
        shutil.rmtree(folder_path)
        return {'success': True, 'deleted': folder_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.post('/api/downloads/{folder_name}/restart')
async def restart_download(folder_name, request: Request):
    data = await request.json() if request else {}
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    # Get URL from landing meta or construct from folder name
    meta_path = folder_path / '_wcloner' / 'landing.json'
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        url = meta.get('url', f'https://{folder_name}')
    else:
        url = data.get('url', f'https://{folder_name}')
    
    engine = data.get('engine', 'wget2')
    options = data.get('options', {
        'recursive': True,
        'depth': 5,
        'page_requisites': True,
        'convert_links': True,
        'no_parent': True,
        'include_subdomains': True,
        'ignore_robots': True
    })
    
    use_wget2 = engine in ['wget2', 'smart']
    
    job_id = str(uuid.uuid4())[:8]
    job = WgetJob(job_id, url, options, use_wget2, folder_name, engine)
    jobs[job_id] = job
    save_jobs()
    
    # Update landing meta
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            meta['download_job_id'] = job_id
            meta['status'] = 'downloading'
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        except:
            pass
    
    start_job_process(job_id)
    return job.to_dict()


# =============================================================================
# API ENDPOINTS - Scanning
# =============================================================================

@app.post('/api/scan')
async def scan_site(request: Request):
    data = await request.json()
    url = data.get('url', '').strip()
    max_pages = data.get('max_pages', 50)
    
    if not url:
        raise HTTPException(status_code=400, detail={'error': 'URL is required'})
    
    result = scan_site_sync(url, max_pages)
    return result


@app.post('/api/scan-async')
async def scan_async_endpoint(request: Request):
    data = await request.json()
    url = data.get('url', '').strip()
    folder_name = data.get('folder_name', '')
    max_pages = data.get('max_pages', 30)
    
    if not url:
        raise HTTPException(status_code=400, detail={'error': 'URL is required'})
    
    scan_id = start_async_scan(url, folder_name, max_pages)
    
    return {
        'scan_id': scan_id,
        'status': 'started',
        'message': 'Scan started in background'
    }


@app.get('/api/scan-status/{scan_id}')
async def get_scan_status_endpoint(scan_id):
    status = get_scan_status(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail={'error': 'Scan not found'})
    return status


# =============================================================================
# API ENDPOINTS - Links Analysis
# =============================================================================

@app.get('/api/downloads/{folder_name}/links-analysis')
async def get_links_analysis_endpoint(folder_name):
    """Получить анализ ссылок для папки (из кэша или локальный анализ)"""
    result = get_links_analysis(folder_name)
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result)
    return result


@app.post('/api/downloads/{folder_name}/analyze-links')
async def analyze_links_endpoint(folder_name, request: Request):
    """Запустить глубокий онлайн анализ ссылок"""
    data = await request.json() if request else {}
    url = data.get('url')
    max_pages = data.get('max_pages', 50)
    
    result = run_deep_analysis(folder_name, url, max_pages)
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result)
    return result


@app.post('/api/downloads/{folder_name}/download-page')
async def download_single_page_endpoint(folder_name, request: Request):
    """Скачать конкретную страницу по URL"""
    import requests as http_requests
    
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json()
    url = data.get('url', '').strip()
    force = data.get('force', False)
    
    if not url:
        raise HTTPException(status_code=400, detail={'error': 'URL is required'})
    
    # Parse URL to get domain and path
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.lstrip('/') or 'index.html'
    
    # Add index.html if path is directory
    if path.endswith('/') or '.' not in path.split('/')[-1]:
        path = path.rstrip('/') + '/index.html'
    
    local_file = folder_path / domain / path
    
    # Check if exists
    if local_file.exists() and not force:
        return {'status': 'skipped', 'reason': 'File already exists', 'path': str(local_file.relative_to(folder_path))}
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        response = http_requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200:
            local_file.parent.mkdir(parents=True, exist_ok=True)
            with open(local_file, 'wb') as f:
                f.write(response.content)
            
            return {
                'status': 'downloaded',
                'path': str(local_file.relative_to(folder_path)),
                'size': len(response.content),
                'url': url
            }
        else:
            return {'status': 'failed', 'error': f'HTTP {response.status_code}', 'url': url}
    
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'url': url}


# =============================================================================
# API ENDPOINTS - Dynamic Content Download (Puppeteer)
# =============================================================================

@app.post('/api/downloads/{folder_name}/scan-dynamic')
async def scan_dynamic_content(folder_name, request: Request):
    """
    Сканирует страницу через Puppeteer и докачивает динамически загружаемые ресурсы.
    Полезно для сайтов с lazy loading, JS-генерируемым контентом.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json() if request else {}
    url = data.get('url', '').strip()
    timeout = data.get('timeout', 30)
    
    if not url:
        # Используем URL из метаданных
        meta_path = folder_path / '_wcloner' / 'landing.json'
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            url = meta.get('url', f'https://{folder_name}')
        else:
            url = f'https://{folder_name}'
    
    result = scan_page_for_missing(url, folder_path, timeout)
    return result


@app.post('/api/downloads/{folder_name}/scan-dynamic-multiple')
async def scan_dynamic_multiple(folder_name, request: Request):
    """
    Сканирует несколько страниц через Puppeteer и докачивает ресурсы.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json()
    urls = data.get('urls', [])
    timeout = data.get('timeout', 30)
    
    if not urls:
        raise HTTPException(status_code=400, detail={'error': 'URLs list is required'})
    
    result = scan_multiple_pages(urls, folder_path, timeout)
    return result


@app.get('/api/downloads/{folder_name}/quick-scan-missing')
async def quick_scan_missing(folder_name):
    """
    Быстрое сканирование HTML на предмет недостающих ресурсов (без Puppeteer).
    Парсит HTML и проверяет существование файлов локально.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    result = quick_scan_missing_resources(folder_path)
    return result


# =============================================================================
# API ENDPOINTS - Page Checker (404 Analysis)
# =============================================================================

@app.get('/api/downloads/{folder_name}/check-local-links')
async def check_local_links_endpoint(folder_name):
    """
    Проверяет локальные ссылки в HTML файлах.
    Находит битые ссылки (файлы которых нет локально).
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    result = check_local_links(folder_path)
    return result


@app.post('/api/downloads/{folder_name}/check-pages-online')
async def check_pages_online_endpoint(folder_name, request: Request):
    """
    Проверяет список URL онлайн на 404 и другие ошибки.
    Анализирует причины ошибок и предлагает решения.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json()
    urls = data.get('urls', [])
    
    if not urls:
        raise HTTPException(status_code=400, detail={'error': 'URLs list is required'})
    
    result = check_pages_online(urls, folder_path)
    return result


@app.post('/api/downloads/{folder_name}/check-all-internal')
async def check_all_internal_endpoint(folder_name, request: Request):
    """
    Полная проверка: находит все внутренние ссылки и проверяет их онлайн.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json() if request else {}
    base_url = data.get('url')
    max_pages = data.get('max_pages', 50)
    
    result = check_all_internal_links(folder_path, base_url, max_pages)
    return result


@app.post('/api/downloads/{folder_name}/download-working-pages')
async def download_working_pages_endpoint(folder_name, request: Request):
    """
    Докачивает страницы которые работают онлайн но отсутствуют локально.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json()
    check_results = data.get('check_results', {})
    max_download = data.get('max_download', 20)
    
    result = download_working_pages(folder_path, check_results, max_download)
    return result


@app.post('/api/downloads/{folder_name}/fix-broken-links')
async def fix_broken_links_endpoint(folder_name, request: Request):
    """
    Пытается исправить битые ссылки (скачать по редиректам).
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    data = await request.json()
    check_results = data.get('check_results', {})
    
    result = fix_broken_links(folder_path, check_results)
    return result


@app.get('/api/downloads/{folder_name}/page-check-summary')
async def page_check_summary_endpoint(folder_name):
    """
    Возвращает краткую сводку по проверке страниц.
    """
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    result = get_page_check_summary(folder_path)
    return result


# =============================================================================
# API ENDPOINTS - Landing Preparation
# =============================================================================

@app.post('/api/prepare-landing')
async def prepare_landing(request: Request):
    data = await request.json()
    url = data.get('url', '').strip()
    
    if not url:
        raise HTTPException(status_code=400, detail={'error': 'URL is required'})
    
    result = prepare_landing_folder(url)
    return result


@app.post('/api/start-download-selected')
async def start_download_selected(request: Request):
    data = await request.json()
    folder_name = data.get('folder_name')
    url = data.get('url')
    selected_domains = data.get('selected_domains', [])
    domains_with_engines = data.get('domains_with_engines', [])
    engine = data.get('engine', 'wget2')
    options = data.get('options', {})
    
    if not folder_name or not url:
        raise HTTPException(status_code=400, detail={'error': 'folder_name and url required'})
    
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    # Update landing metadata
    meta_path = folder_path / '_wcloner' / 'landing.json'
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            meta['selected_domains'] = selected_domains
            meta['domains_with_engines'] = domains_with_engines
            meta['default_engine'] = engine
            meta['status'] = 'downloading'
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        except:
            pass
    
    # Build job options
    job_options = {
        'recursive': True,
        'depth': options.get('depth', 5),
        'page_requisites': True,
        'convert_links': True,
        'no_parent': True,
        'include_subdomains': True,
        'ignore_robots': True,
        'extra_domains': selected_domains
    }
    
    job_id = str(uuid.uuid4())[:8]
    use_wget2 = engine in ['wget2', 'smart']
    
    job = WgetJob(job_id, url, job_options, use_wget2, folder_name, engine)
    jobs[job_id] = job
    save_jobs()
    
    # Update landing with job id
    if meta_path.exists():
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            meta['download_job_id'] = job_id
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        except:
            pass
    
    start_job_process(job_id)
    return job.to_dict()


@app.get('/api/landing-status/{folder_name}')
async def get_landing_status(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    meta_path = folder_path / '_wcloner' / 'landing.json'
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Landing metadata not found'})
    
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    
    # Check job status
    job_id = meta.get('download_job_id')
    job_status = None
    if job_id and job_id in jobs:
        job = jobs[job_id]
        job_status = job.to_dict()
    
    return {
        'landing_meta': meta,
        'job': job_status
    }


# =============================================================================
# API ENDPOINTS - Integrity & Changes
# =============================================================================

@app.get('/api/downloads/{folder_name}/check-changes')
async def check_changes_endpoint(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    meta_path = folder_path / '_wcloner' / 'landing.json'
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        url = meta.get('url', f'https://{folder_name}')
    else:
        url = f'https://{folder_name}'
    
    result = check_site_changes(folder_path, url)
    return result


@app.get('/api/downloads/{folder_name}/check-integrity')
async def check_integrity_endpoint(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    result = check_site_integrity(folder_path)
    return result


@app.post('/api/download-missing/{folder_name}')
async def download_missing_endpoint(folder_name, request: Request):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    # Parse request body
    data = {}
    try:
        data = await request.json()
    except:
        pass
    
    # Get paths from request or use integrity check
    paths = data.get('paths', [])
    force = data.get('force', False)
    
    if not paths:
        # Fallback to integrity check
        integrity = check_site_integrity(folder_path)
        paths = [m['missing'] for m in integrity.get('missing_files', [])]
    
    if not paths:
        return {'message': 'No files to download', 'downloaded': 0}
    
    # Get base URL from metadata
    meta_path = folder_path / '_wcloner' / 'landing.json'
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        base_url = meta.get('url', f'https://{folder_name}')
    else:
        base_url = f'https://{folder_name}'
    
    result = download_missing_files(folder_path, base_url, paths[:50], force=force)
    return result


# =============================================================================
# API ENDPOINTS - File Tree & Scripts Status
# =============================================================================

@app.get('/api/file-tree/{folder_name}')
async def get_file_tree(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    def build_tree(path, prefix=''):
        items = []
        try:
            for item in sorted(path.iterdir()):
                if item.name.startswith('.') or item.name in ['node_modules', '__pycache__']:
                    continue
                
                rel_path = str(item.relative_to(folder_path))
                
                if item.is_dir():
                    items.append({
                        'name': item.name,
                        'path': rel_path,
                        'type': 'directory',
                        'children': build_tree(item, prefix + '  ')
                    })
                else:
                    items.append({
                        'name': item.name,
                        'path': rel_path,
                        'type': 'file',
                        'size': item.stat().st_size
                    })
        except:
            pass
        return items
    
    return build_tree(folder_path)


@app.get('/api/downloads/{folder_name}/trackers')
async def scan_trackers_endpoint(folder_name):
    """Scan downloaded site for tracking scripts without removing them."""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    from modules.html_cleaner import scan_trackers
    return scan_trackers(folder_path)


@app.post('/api/downloads/{folder_name}/fix-html')
async def fix_html_endpoint(folder_name):
    """Fix wget2 -k HTML corruption: removes URLs inserted inside words/attributes."""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    from modules.html_fixer import fix_wget_corrupted_html
    return fix_wget_corrupted_html(folder_path)


@app.post('/api/downloads/{folder_name}/fix-html-scan')
async def fix_html_scan_endpoint(folder_name):
    """Dry-run scan: show what would be fixed without modifying files."""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    from modules.html_fixer import fix_wget_corrupted_html
    return fix_wget_corrupted_html(folder_path, dry_run=True)


@app.get('/api/downloads/{folder_name}/broken-links')
async def get_broken_links(folder_name):
    """Получить список битых ссылок и анализ возможности исправления."""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    # Сначала проверяем локальные ссылки
    broken = check_local_links(folder_path, max_pages=200)
    
    # Анализируем возможность исправления
    from modules.link_fixer import analyze_broken_links
    analysis = analyze_broken_links(folder_path, broken.get('broken_links', []))
    
    return {
        'check_result': broken,
        'analysis': analysis
    }


@app.post('/api/downloads/{folder_name}/fix-broken-links')
async def fix_broken_links_endpoint(folder_name, request: Request):
    """Исправить битые ссылки (локальные или скачать недостающие)."""
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    body = await request.json()
    action = body.get('action', 'auto')  # auto, fix_local, download
    links_to_fix = body.get('links', [])
    
    from modules.link_fixer import auto_fix_local_links, fix_broken_links as fix_links
    
    if action == 'auto':
        # Автоматически исправляем все что можно локально
        broken = check_local_links(folder_path, max_pages=200)
        result = auto_fix_local_links(folder_path, broken.get('broken_links', []))
        return result
    elif action == 'fix_local':
        # Исправляем только указанные ссылки
        result = fix_links(folder_path, links_to_fix)
        return result
    elif action == 'download':
        # Скачиваем недостающие файлы
        downloaded = []
        failed = []
        for link_info in links_to_fix:
            link = link_info.get('link', '')
            if link.startswith(('http://', 'https://')):
                from modules.page_checker import download_single_page
                result = download_single_page(link, folder_path)
                if result.get('success'):
                    downloaded.append({**link_info, 'path': result.get('path')})
                else:
                    failed.append({**link_info, 'error': result.get('error')})
        return {'downloaded': downloaded, 'failed': failed}
    else:
        raise HTTPException(status_code=400, detail={'error': 'Invalid action'})


@app.get('/api/downloads/{folder_name}/scripts-status')
async def get_scripts_status(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    vue_dir = folder_path / 'vue-app'
    backend_server = folder_path / 'backend-server.js'
    
    # Check for HTML content (in root or domain subdirectories)
    has_content = any(folder_path.glob('*.html')) or any(folder_path.glob('*/*.html'))
    
    return {
        'vue_wrapper': {
            'ready': vue_dir.exists() and (vue_dir / 'package.json').exists(),
            'has_node_modules': (vue_dir / 'node_modules').exists() if vue_dir.exists() else False
        },
        'backend_server': {
            'ready': backend_server.exists()
        },
        'site_content': {
            'ready': has_content
        }
    }


@app.get('/api/downloads/{folder_name}/servers-status')
async def get_servers_status_alt(folder_name):
    return get_servers_status(folder_name)


@app.get('/api/thumbnail/{folder_name}')
async def get_thumbnail_alt(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    preview_path = folder_path / 'preview.png'
    if preview_path.exists():
        return FileResponse(preview_path, media_type='image/png')
    
    raise HTTPException(status_code=404, detail={'error': 'No preview available'})


@app.get('/api/find-index/{folder_name}')
async def find_index(folder_name: str):
    """Find the main index.html file in a downloaded site folder"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    index_file = find_index_file(folder_path)
    
    if index_file:
        # Return relative path from folder
        rel_path = index_file.relative_to(folder_path)
        return {
            'found': True,
            'path': str(rel_path),
            'full_path': str(index_file),
            'url': f'/api/browse/{folder_name}/{rel_path}'
        }
    
    raise HTTPException(status_code=404, detail={'error': 'No index.html found'})


@app.get('/api/browse/{folder_name}/{filepath:path}')
async def browse_file(folder_name, filepath: str):
    folder_path = DOWNLOADS_DIR / folder_name
    
    # Try multiple locations
    possible_paths = [
        folder_path / filepath,
        folder_path / folder_name / filepath,  # domain subfolder
    ]
    
    # If looking for index.html, also search recursively
    if filepath == 'index.html':
        # Check vue-app for preview
        vue_index = folder_path / 'vue-app' / 'index.html'
        if vue_index.exists():
            possible_paths.insert(0, vue_index)
        
        # Find any index.html
        for html_file in folder_path.rglob('index.html'):
            if 'node_modules' not in str(html_file) and 'vue-app' not in str(html_file):
                possible_paths.append(html_file)
                break
    
    for file_path in possible_paths:
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
    
    # Return placeholder HTML if no content yet
    if filepath == 'index.html':
        placeholder = f"""<!DOCTYPE html>
<html>
<head><title>{folder_name}</title></head>
<body style="display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#1a1a2e;color:#fff;font-family:system-ui;">
<div style="text-align:center;">
<h2>📥 Сайт ещё не скачан</h2>
<p>Нажмите "Выбрать и скачать" чтобы начать</p>
</div>
</body>
</html>"""
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=placeholder)
    
    raise HTTPException(status_code=404, detail={'error': 'File not found'})


# =============================================================================
# API ENDPOINTS - Servers
# =============================================================================

@app.get('/api/downloads/{folder_name}/servers')
async def get_servers_status_endpoint(folder_name):
    return get_servers_status(folder_name)


@app.post('/api/downloads/{folder_name}/start-vue')
async def start_vue_server_endpoint(folder_name):
    result = start_vue_server(folder_name)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post('/api/downloads/{folder_name}/start-backend')
async def start_backend_server_endpoint(folder_name):
    result = start_backend_server(folder_name)
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post('/api/downloads/{folder_name}/stop-servers')
async def stop_servers_endpoint(folder_name):
    return stop_servers(folder_name)


@app.post('/api/downloads/{folder_name}/stop-vue')
async def stop_vue_server_endpoint(folder_name):
    """Stop only Vue server for this folder"""
    return stop_vue_server(folder_name)


@app.post('/api/downloads/{folder_name}/generate-scripts')
async def generate_scripts_endpoint(folder_name, request: Request):
    data = await request.json() if request else {}
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    port = data.get('port', 3000)
    vue_wrapper = data.get('vue_wrapper', True)
    
    success = generate_vue_wrapper(folder_path, folder_name, port, port + 1)
    
    if success:
        return {'success': True, 'message': 'Scripts generated'}
    else:
        raise HTTPException(status_code=500, detail={'error': 'Failed to generate scripts'})


# =============================================================================
# API ENDPOINTS - Screenshots
# =============================================================================

@app.get('/api/downloads/{folder_name}/thumbnail')
async def get_thumbnail(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    preview_path = folder_path / 'preview.png'
    if preview_path.exists():
        return FileResponse(preview_path, media_type='image/png')
    
    raise HTTPException(status_code=404, detail={'error': 'No preview available'})


@app.post('/api/screenshot/{folder_name}')
async def create_screenshot_endpoint(folder_name):
    folder_path = DOWNLOADS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    preview_path = generate_preview_screenshot(folder_path, folder_name, folder_name)
    
    if preview_path:
        return {'success': True, 'path': str(preview_path)}
    else:
        raise HTTPException(status_code=500, detail={'error': 'Failed to generate screenshot'})


# =============================================================================
# API ENDPOINTS - Config
# =============================================================================

@app.get('/api/open-folder')
async def open_folder(path: str = None, folder_name: str = None):
    """Open folder in system file manager (Finder on macOS)"""
    import subprocess
    import platform
    
    # Determine the path to open
    if path:
        folder_path = Path(path)
    elif folder_name:
        folder_path = DOWNLOADS_DIR / folder_name
    else:
        raise HTTPException(status_code=400, detail={'error': 'path or folder_name required'})
    
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail={'error': 'Folder not found'})
    
    # Open in system file manager
    system = platform.system()
    try:
        if system == 'Darwin':  # macOS
            subprocess.Popen(['open', str(folder_path)])
        elif system == 'Windows':
            subprocess.Popen(['explorer', str(folder_path)])
        else:  # Linux
            subprocess.Popen(['xdg-open', str(folder_path)])
        return {'success': True, 'path': str(folder_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail={'error': str(e)})


@app.get('/api/config')
async def get_config():
    return {
        'downloads_dir': str(DOWNLOADS_DIR),
        'wget2_path': WGET2_PATH,
        'wget2_available': Path(WGET2_PATH).exists()
    }


@app.post('/api/landings/config')
async def save_landing_config_endpoint(request: Request):
    data = await request.json()
    config_key = data.get('config_key', '')
    settings = data.get('settings', {})
    
    if not config_key:
        raise HTTPException(status_code=400, detail={'error': 'config_key is required'})
    
    landings_config = load_landings_config()
    landings_config[config_key] = settings
    save_landings_config(landings_config)
    
    return {'success': True}


# =============================================================================
# Static Files & SPA Routes
# =============================================================================

@app.get('/')
async def index():
    return FileResponse(Path(__file__).parent / 'static' / 'dist' / 'index.html')


@app.get('/landings')
@app.get('/download')
@app.get('/site/{path:path}')
async def spa_routes(path: str = ''):
    return FileResponse(Path(__file__).parent / 'static' / 'dist' / 'index.html')


@sio.event
async def connect(sid, environ):
    print('Client connected:', sid)


# Mount static files
app.mount("/assets", StaticFiles(directory=Path(__file__).parent / "static" / "dist" / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


if __name__ == '__main__':
    import uvicorn
    print(f"Wget Admin starting (FastAPI)...")
    print(f"Using wget2: {WGET2_PATH}")
    print(f"Downloads dir: {DOWNLOADS_DIR}")
    load_jobs()
    uvicorn.run(socket_app, host='0.0.0.0', port=9000)
