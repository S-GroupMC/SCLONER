"""
Downloader module - WgetJob class and download engines
"""
import subprocess
import threading
import multiprocessing
import os
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .config import (
    DOWNLOADS_DIR, WGET2_PATH, HTTRACK_PATH, PUPPETEER_SCRIPT,
    TOOL_ENV, jobs, save_jobs
)


# Blocked domains - analytics, tracking, ads
BLOCKED_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com', 'googlesyndication.com',
    'doubleclick.net', 'facebook.net', 'facebook.com/tr', 'fbcdn.net',
    'twitter.com/i/', 'analytics.twitter.com', 't.co',
    'linkedin.com/px', 'snap.licdn.com',
    'hotjar.com', 'mouseflow.com', 'crazyegg.com', 'luckyorange.com',
    'mixpanel.com', 'amplitude.com', 'segment.io', 'segment.com',
    'intercom.io', 'crisp.chat', 'drift.com', 'zendesk.com',
    'hubspot.com', 'hs-scripts.com', 'hs-analytics.net',
    'optimizely.com', 'abtasty.com', 'vwo.com',
    'newrelic.com', 'nr-data.net', 'sentry.io',
    'ads.', 'ad.', 'tracking.', 'pixel.', 'beacon.',
    'mc.yandex.ru', 'metrika.yandex.ru',
    'connect.facebook.net', 'platform.twitter.com',
    'widgets.pinterest.com', 'assets.pinterest.com',
    'static.ads-twitter.com', 'analytics.tiktok.com',
    'bat.bing.com', 'clarity.ms',
    'onesignal.com', 'pushwoosh.com',
    'recaptcha.net', 'gstatic.com/recaptcha',
    'cookiebot.com', 'cookieconsent.', 'cookie-script.com',
    'trustpilot.com/bootstrap', 'widget.trustpilot.com',
]

# Allowed CDN patterns (only fonts and essential CSS/JS libraries)
ALLOWED_CDN_PATTERNS = [
    'fonts.googleapis.com', 'fonts.gstatic.com',
    'use.fontawesome.com', 'kit.fontawesome.com',
    'stackpath.bootstrapcdn.com', 'maxcdn.bootstrapcdn.com',
    'cdn.tailwindcss.com', 'unpkg.com',
]


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
        self.pid = None
        self.started_at = None
        self.finished_at = None
        self.stop_requested = False
        self.preview_image = None
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
            'output_lines': self.output_lines[-50:],
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'output_dir': str(self.output_dir),
            'use_wget2': self.use_wget2,
            'engine': self.engine,
            'preview_image': self.preview_image,
            'pid': self.pid
        }


def get_domain_filter_config(job):
    """Build domain filtering configuration for any engine."""
    opts = job.options
    parsed = urlparse(job.url)
    main_domain = parsed.netloc
    
    if main_domain.startswith('www.'):
        base_domain = main_domain[4:]
    else:
        base_domain = main_domain
    
    allowed_domains = set()
    allowed_domains.add(base_domain)
    allowed_domains.add(f'www.{base_domain}')
    allowed_domains.add(main_domain)
    
    if opts.get('include_subdomains', False):
        allowed_domains.add(f'*.{base_domain}')
        # Add common subdomains explicitly for wget2 compatibility
        common_subdomains = ['shop', 'store', 'www', 'cdn', 'static', 'assets', 'media', 'images', 'img']
        for sub in common_subdomains:
            allowed_domains.add(f'{sub}.{base_domain}')
    
    extra_domains = opts.get('extra_domains', '')
    if extra_domains:
        if isinstance(extra_domains, list):
            for d in extra_domains:
                if d:
                    allowed_domains.add(d.strip())
        else:
            for d in extra_domains.split(','):
                d = d.strip()
                if d:
                    allowed_domains.add(d)
    
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
    for blocked in filter_config['blocked_domains']:
        if blocked in domain:
            return False
    
    base = filter_config['base_domain']
    if domain == base or domain.endswith(f'.{base}'):
        return True
    
    for allowed in filter_config['allowed_domains']:
        if allowed.startswith('*.'):
            pattern = allowed[2:]
            if domain == pattern or domain.endswith(f'.{pattern}'):
                return True
        elif domain == allowed:
            return True
    
    for cdn in filter_config['allowed_cdn']:
        if domain == cdn or domain.endswith(f'.{cdn}'):
            return True
    
    return False


def build_wget_command(job):
    """Build wget2 command from job options"""
    cmd = [WGET2_PATH]
    cmd.append('--http2')
    cmd.append('--compression=br,gzip,zstd')
    cmd.append('--tcp-fastopen')
    cmd.append('--dns-cache')
    cmd.append('--hsts')
    
    if job.options.get('progress_bar', True):
        cmd.append('--progress=bar')
    
    threads = job.options.get('parallel_threads', 10)
    cmd.extend(['--max-threads', str(threads)])
    
    http2_window = job.options.get('http2_window', 30)
    cmd.extend(['--http2-request-window', str(http2_window)])
    
    opts = job.options
    
    if opts.get('recursive', False):
        cmd.append('-r')
        depth = opts.get('depth', 2)
        cmd.extend(['-l', str(depth)])
    
    if opts.get('page_requisites', True):
        cmd.append('-p')
    
    if opts.get('convert_links', True):
        cmd.append('-k')
    
    if opts.get('adjust_extensions', True):
        cmd.append('-E')
    
    # Cut query strings from filenames for cleaner local paths
    if opts.get('cut_get_vars', True):
        cmd.append('--cut-file-get-vars')
    
    filter_config = get_domain_filter_config(job)
    base_domain = filter_config['base_domain']
    
    domains_list = [base_domain, f'www.{base_domain}']
    
    if opts.get('include_subdomains', False):
        domains_list.append(f'.{base_domain}')
    
    for domain in filter_config['allowed_domains']:
        if domain not in domains_list and not domain.startswith('*.'):
            domains_list.append(domain)
    
    for cdn in filter_config['allowed_cdn']:
        if cdn not in domains_list:
            domains_list.append(cdn)
    
    cmd.extend(['-D', ','.join(domains_list)])
    
    reject_domains = ','.join([f'*{d}*' for d in filter_config['blocked_domains'][:20]])
    cmd.extend(['--reject-regex', reject_domains])
    
    # Only span hosts if explicitly enabled AND only for allowed domains
    # By default, stay on the same domain to avoid downloading external sites
    if opts.get('span_hosts', False):
        cmd.append('-H')
    
    if opts.get('no_parent', True):
        cmd.append('--no-parent')
    
    rate_limit = opts.get('rate_limit', '')
    if rate_limit:
        cmd.extend(['--limit-rate', rate_limit])
    
    wait = opts.get('wait', 0.5)
    if wait:
        cmd.extend(['--wait', str(wait)])
    
    if opts.get('random_wait', False):
        cmd.append('--random-wait')
    
    user_agent = opts.get('user_agent', '')
    if user_agent:
        cmd.extend(['--user-agent', user_agent])
    
    reject = opts.get('reject', '')
    if reject:
        cmd.extend(['--reject', reject])
    
    accept = opts.get('accept', '')
    if accept:
        cmd.extend(['--accept', accept])
    
    timeout = opts.get('timeout', 30)
    cmd.extend(['--timeout', str(timeout)])
    
    retries = opts.get('retries', 3)
    cmd.extend(['--tries', str(retries)])
    
    if opts.get('restrict_file_names', True):
        cmd.append('--restrict-file-names=windows')
    
    if opts.get('trust_server_names', True):
        cmd.append('--trust-server-names')
    
    if opts.get('ignore_robots', False):
        cmd.append('--robots=off')
    
    if opts.get('no_cookies', False):
        cmd.append('--no-cookies')
    
    if opts.get('mirror_mode', False):
        cmd.append('--mirror')
    
    if opts.get('continue_download', False):
        cmd.append('--timestamping')
    
    # Don't use --no-clobber as it causes wget2 to exit with error when files exist
    # Use --timestamping instead for incremental downloads
    if opts.get('timestamping', False):
        cmd.append('--timestamping')
    
    # Note: wget2 creates host directories by default (e.g., eagles.com/)
    # We handle this in the server configuration
    
    cmd.extend(['-P', str(job.output_dir)])
    cmd.append('--progress=dot:default')
    cmd.append(job.url)
    
    return cmd


def build_httrack_command(job):
    """Build httrack command from job options"""
    cmd = [HTTRACK_PATH]
    opts = job.options
    
    filter_config = get_domain_filter_config(job)
    base_domain = filter_config['base_domain']
    
    cmd.append(job.url)
    cmd.extend(['-O', str(job.output_dir)])
    
    depth = opts.get('depth', 2)
    cmd.extend(['-r' + str(depth)])
    
    cmd.append('-%e0')
    cmd.append('--near')
    cmd.append('--robots=0')
    cmd.append('--keep-alive')
    
    if opts.get('include_subdomains', False):
        cmd.append(f'+*.{base_domain}/*')
        cmd.append(f'+{base_domain}/*')
        cmd.append(f'+www.{base_domain}/*')
    else:
        cmd.append(f'+{filter_config["main_domain"]}/*')
    
    for domain in filter_config['allowed_domains']:
        if not domain.startswith('*.') and domain != base_domain and domain != f'www.{base_domain}':
            cmd.append(f'+{domain}/*')
    
    for cdn in filter_config['allowed_cdn']:
        cmd.append(f'+{cdn}/*')
    
    for blocked in filter_config['blocked_domains']:
        cmd.append(f'-*{blocked}*')
    
    cmd.append('-*')
    
    user_agent = opts.get('user_agent', '')
    if user_agent:
        cmd.extend(['-F', user_agent])
    
    timeout = opts.get('timeout', 30)
    cmd.extend(['-T', str(timeout)])
    
    retries = opts.get('retries', 3)
    cmd.extend(['-R', str(retries)])
    
    if opts.get('continue_download', False):
        cmd.append('--continue')
    
    cmd.append('-v')
    
    return cmd


def build_puppeteer_command(job):
    """Build puppeteer crawler command from job options"""
    cmd = ['node', str(PUPPETEER_SCRIPT)]
    opts = job.options
    
    cmd.append(job.url)
    cmd.append(str(job.output_dir))
    
    max_pages = opts.get('max_pages', 100)
    cmd.append(str(max_pages))
    
    if opts.get('js_scroll', True):
        cmd.append('--scroll')
    
    if opts.get('js_click_more', True):
        cmd.append('--click-more')
    
    wait_time = opts.get('js_wait', 2000)
    cmd.append(f'--wait={wait_time}')
    
    depth = opts.get('depth', 3)
    cmd.append(f'--depth={depth}')
    
    return cmd


def update_job_stats(job):
    """Update job statistics from output"""
    if not job.output_dir.exists():
        return
    
    try:
        files = list(job.output_dir.rglob('*'))
        job.files_downloaded = len([f for f in files if f.is_file()])
        total_bytes = sum(f.stat().st_size for f in files if f.is_file())
        
        from .utils import format_size
        job.total_size = format_size(total_bytes)
    except:
        pass


def run_single_engine(job, engine_name, cmd):
    """Run a single engine and return success status"""
    job.output_lines.append(f"")
    job.output_lines.append(f"{'='*50}")
    job.output_lines.append(f"Running: {engine_name}")
    job.output_lines.append(f"Command: {' '.join(cmd)}")
    job.output_lines.append(f"{'='*50}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=TOOL_ENV
        )
        job.process = process
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                job.output_lines.append(line)
                update_job_stats(job)
        
        process.wait()
        return process.returncode == 0
    except Exception as e:
        job.output_lines.append(f"Error in {engine_name}: {str(e)}")
        return False


def cleanup_external_domains(job):
    """Remove folders of external domains"""
    filter_config = get_domain_filter_config(job)
    
    if not job.output_dir.exists():
        return
    
    removed_count = 0
    for folder in job.output_dir.iterdir():
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        
        if folder_name in ('hts-cache', 'hts-log.txt', 'cookies.txt', '_wcloner', 'vue-app', '_site'):
            continue
        
        if not is_domain_allowed(folder_name, filter_config):
            try:
                shutil.rmtree(folder)
                removed_count += 1
                job.output_lines.append(f"[Cleanup] Removed external: {folder_name}")
            except Exception as e:
                job.output_lines.append(f"[Cleanup] Error removing {folder_name}: {e}")
    
    if removed_count > 0:
        job.output_lines.append(f"[Cleanup] Removed {removed_count} external domain folders")


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
        save_jobs()
        
        if not job.stop_requested:
            cmd_wget2 = build_wget_command(job)
            run_single_engine(job, "wget2 (static content)", cmd_wget2)
        
        if not job.stop_requested:
            cmd_puppeteer = build_puppeteer_command(job)
            run_single_engine(job, "Puppeteer (JS rendering)", cmd_puppeteer)
        
        if not job.stop_requested:
            cmd_httrack = build_httrack_command(job)
            run_single_engine(job, "HTTrack (final pass)", cmd_httrack)
        
        if job.stop_requested:
            job.output_lines.append("")
            job.output_lines.append("SMART MODE STOPPED by user")
        else:
            job.status = 'completed'
            job.finished_at = datetime.now()
            job.output_lines.append("")
            job.output_lines.append("SMART MODE COMPLETED - All engines finished")
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
    save_jobs()
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=TOOL_ENV
        )
        job.process = process
        
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                job.output_lines.append(line)
                update_job_stats(job)
        
        process.wait()
        returncode = process.returncode
        job.output_lines.append(f"[Debug] wget2 exit code: {returncode}")
        
        cleanup_external_domains(job)
        update_job_stats(job)  # Update stats before checking
        
        job.output_lines.append(f"[Debug] Files downloaded: {job.files_downloaded}")
        
        # wget2 return codes: 0=success, 8=some files failed (partial success)
        # Consider job completed if we downloaded any files
        if returncode == 0 or job.files_downloaded > 0:
            job.status = 'completed'
        else:
            job.status = 'failed'
        job.finished_at = datetime.now()
        update_job_stats(job)
        
        # Auto-generate preview screenshot and clean HTML
        if job.status == 'completed':
            try:
                # Clean HTML: remove trackers and fix internal links
                from .html_cleaner import clean_downloaded_site
                parsed = urlparse(job.url)
                main_domain = parsed.netloc.replace('www.', '')
                
                job.output_lines.append("[WCLoner] Очистка HTML от трекеров...")
                stats = clean_downloaded_site(job.output_dir, main_domain)
                
                if stats.get('error'):
                    job.output_lines.append(f"[WCLoner] ⚠️ {stats['error']}")
                else:
                    job.output_lines.append(f"[WCLoner] ✅ Обработано {stats['modified_files']}/{stats['total_files']} файлов")
                    if stats['trackers_removed'] > 0:
                        job.output_lines.append(f"[WCLoner] ✅ Удалено трекеров: {stats['trackers_removed']}")
                    if stats['links_rewritten'] > 0:
                        job.output_lines.append(f"[WCLoner] ✅ Исправлено ссылок: {stats['links_rewritten']}")
                    if stats['downloaded_domains']:
                        job.output_lines.append(f"[WCLoner] 📁 Домены: {', '.join(stats['downloaded_domains'])}")
            except Exception as e:
                job.output_lines.append(f"[WCLoner] ❌ Ошибка очистки HTML: {str(e)}")
            
            try:
                from .file_manager import generate_preview_screenshot
                parsed = urlparse(job.url)
                main_domain = parsed.netloc.replace('www.', '')
                
                job.output_lines.append("[WCLoner] Создание preview screenshot...")
                
                preview_path = generate_preview_screenshot(
                    folder_path=job.output_dir,
                    main_domain=main_domain,
                    job_id=job.id
                )
                
                if preview_path:
                    job.output_lines.append(f"[WCLoner] ✅ Preview создан: {preview_path.name}")
                    job.preview_image = f"/static/previews/{preview_path.name}"
                else:
                    job.output_lines.append("[WCLoner] ⚠️ Preview не создан")
            except Exception as e:
                job.output_lines.append(f"[WCLoner] ❌ Ошибка preview: {str(e)}")
        
    except Exception as e:
        job.status = 'failed'
        job.output_lines.append(f"Error: {str(e)}")
        job.finished_at = datetime.now()
    
    save_jobs()


def start_job_thread(job_id):
    """Start download job in a background thread with separate process for wget"""
    thread = threading.Thread(target=run_wget_job, args=(job_id,))
    thread.daemon = True
    thread.start()


def start_job_process(job_id):
    """Start download job as a completely separate process"""
    job = jobs.get(job_id)
    if not job:
        return None
    
    # Build command
    if job.engine == 'puppeteer':
        cmd = build_puppeteer_command(job)
    elif job.engine == 'httrack':
        cmd = build_httrack_command(job)
    else:
        cmd = build_wget_command(job)
    
    job.output_lines.append(f"Engine: {job.engine}")
    job.output_lines.append(f"Command: {' '.join(cmd)}")
    job.status = 'running'
    job.started_at = datetime.now()
    save_jobs()
    
    # Create log file for output
    log_dir = job.output_dir / '_wcloner'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'wget_{job.id}.log'
    
    # Start subprocess with shell redirect to avoid buffer issues
    try:
        # Use shell to redirect output to file
        cmd_str = ' '.join(f'"{c}"' if ' ' in c else c for c in cmd)
        shell_cmd = f'{cmd_str} > "{log_file}" 2>&1'
        
        process = subprocess.Popen(
            shell_cmd,
            shell=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=TOOL_ENV,
            start_new_session=True
        )
        job.process = process
        job.pid = process.pid
        job.output_lines.append(f"[Process] Started with PID: {process.pid}")
        job.output_lines.append(f"[Process] Log file: {log_file}")
        save_jobs()
        
        # Monitor in background thread - watch process and log file
        def monitor():
            import time
            last_pos = 0
            
            # Wait for process to complete while reading logs
            while process.poll() is None:
                try:
                    if log_file.exists():
                        with open(log_file, 'r') as f:
                            f.seek(last_pos)
                            new_content = f.read()
                            new_pos = f.tell()
                        
                        if new_content:
                            for line in new_content.strip().split('\n'):
                                if line.strip():
                                    job.output_lines.append(line.strip())
                            last_pos = new_pos
                            update_job_stats(job)
                except Exception as e:
                    pass
                
                time.sleep(1)
            
            # Process finished - read remaining output
            try:
                with open(log_file, 'r') as f:
                    f.seek(last_pos)
                    remaining = f.read()
                    for line in remaining.strip().split('\n'):
                        if line.strip():
                            job.output_lines.append(line.strip())
            except:
                pass
            
            returncode = process.returncode
            job.output_lines.append(f"[Process] Finished with code: {returncode}")
            
            cleanup_external_domains(job)
            update_job_stats(job)
            
            # Determine success by return code or files downloaded
            if returncode == 0 or job.files_downloaded > 0:
                job.status = 'completed'
            elif job.stop_requested:
                job.status = 'stopped'
            else:
                job.status = 'failed'
            job.finished_at = datetime.now()
            
            # Auto-generate preview and clean HTML
            if job.status == 'completed':
                try:
                    # Clean HTML: remove trackers and fix internal links
                    from .html_cleaner import clean_downloaded_site
                    parsed = urlparse(job.url)
                    main_domain = parsed.netloc.replace('www.', '')
                    
                    job.output_lines.append("[WCLoner] Очистка HTML от трекеров...")
                    stats = clean_downloaded_site(job.output_dir, main_domain)
                    
                    if stats.get('error'):
                        job.output_lines.append(f"[WCLoner] ⚠️ {stats['error']}")
                    else:
                        job.output_lines.append(f"[WCLoner] ✅ Обработано {stats['modified_files']}/{stats['total_files']} файлов")
                        if stats['trackers_removed'] > 0:
                            job.output_lines.append(f"[WCLoner] ✅ Удалено трекеров: {stats['trackers_removed']}")
                        if stats['links_rewritten'] > 0:
                            job.output_lines.append(f"[WCLoner] ✅ Исправлено ссылок: {stats['links_rewritten']}")
                        if stats['downloaded_domains']:
                            job.output_lines.append(f"[WCLoner] 📁 Домены: {', '.join(stats['downloaded_domains'])}")
                except Exception as e:
                    job.output_lines.append(f"[WCLoner] ❌ Ошибка очистки HTML: {e}")
                
                try:
                    from .file_manager import generate_preview_screenshot
                    parsed = urlparse(job.url)
                    main_domain = parsed.netloc.replace('www.', '')
                    preview_path = generate_preview_screenshot(
                        folder_path=job.output_dir,
                        main_domain=main_domain,
                        job_id=job.id
                    )
                    if preview_path:
                        job.output_lines.append(f"[WCLoner] ✅ Preview: {preview_path.name}")
                except Exception as e:
                    job.output_lines.append(f"[WCLoner] ❌ Preview error: {e}")
            
            save_jobs()
        
        thread = threading.Thread(target=monitor)
        thread.daemon = True
        thread.start()
        
        return process.pid
    except Exception as e:
        job.status = 'failed'
        job.output_lines.append(f"Error starting process: {str(e)}")
        job.finished_at = datetime.now()
        save_jobs()
        return None
