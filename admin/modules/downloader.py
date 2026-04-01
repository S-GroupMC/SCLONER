"""
Downloader module - WgetJob class and download engines
"""
import subprocess
import threading
import multiprocessing
import os
import re
import shlex
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .config import (
    DOWNLOADS_DIR, WGET2_PATH, HTTRACK_PATH, PUPPETEER_SCRIPT,
    TOOL_ENV, jobs, save_jobs
)


# Blocked domains - analytics, tracking, ads
# Matched by exact domain or as suffix (.domain), never as substring
BLOCKED_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com', 'googlesyndication.com',
    'doubleclick.net', 'facebook.net', 'fbcdn.net',
    'connect.facebook.net', 'platform.twitter.com',
    'analytics.twitter.com', 'static.ads-twitter.com',
    't.co',
    'snap.licdn.com',
    'hotjar.com', 'mouseflow.com', 'crazyegg.com', 'luckyorange.com',
    'mixpanel.com', 'amplitude.com', 'segment.io', 'segment.com',
    'intercom.io', 'crisp.chat', 'drift.com', 'zendesk.com',
    'hubspot.com', 'hs-scripts.com', 'hs-analytics.net',
    'optimizely.com', 'abtasty.com', 'vwo.com',
    'newrelic.com', 'nr-data.net', 'sentry.io',
    'mc.yandex.ru', 'metrika.yandex.ru',
    'widgets.pinterest.com', 'assets.pinterest.com',
    'analytics.tiktok.com',
    'bat.bing.com', 'clarity.ms',
    'onesignal.com', 'pushwoosh.com',
    'recaptcha.net',
    'cookiebot.com', 'cookie-script.com',
    'widget.trustpilot.com',
]

# Blocked domain prefixes - match subdomains starting with these
# e.g. 'ads.' matches ads.example.com but NOT myads.com
BLOCKED_DOMAIN_PREFIXES = [
    'ads.', 'ad.', 'tracking.', 'pixel.', 'beacon.', 'cookieconsent.',
]

# Blocked URL path patterns (not domain-level, checked via reject-regex)
BLOCKED_URL_PATHS = [
    r'/tr[?/]',           # facebook.com/tr
    r'/px[?/]',           # linkedin.com/px
    r'/i/jot',            # twitter.com/i/
    r'/recaptcha/',       # gstatic.com/recaptcha
    r'/bootstrap/tp',     # trustpilot.com/bootstrap
]

# Reject URL patterns - useless/duplicate content per platform
REJECT_URL_PATTERNS = [
    # === SHOPIFY ===
    r'/checkouts/',
    r'\.oembed',
    r'/cdn/shopifycloud/',
    r'/cdn/shop/t/\d+/compiled_assets/',
    r'/web-pixels-manager',
    r'\?variant=',
    r'/cart\.js',
    r'/cart/add',
    r'/cart/change',
    r'/search\?',
    r'/account/',
    r'/policies/',
    
    # === RESPONSIVE IMAGE DUPLICATES ===
    # Shopify width params (keep original, reject resized)
    r'[&?]width=(240|352|480|535|600|720|832|940|1066|1200|1400|1600|1800|1920|2048|2560|3000|3200|3840)',
    # Generic responsive image params
    r'[&?]w=(100|150|200|300|400|500|600|700|800|900|1000|1100|1200|1400|1600|1800|2000|2400|2800|3200)',
    r'[&?]size=',
    r'[&?]resize=',
    r'[&?]fit=',
    r'[&?]quality=',
    r'[&?]format=auto',
    
    # === WORDPRESS ===
    r'/wp-admin/',
    r'/wp-login\.php',
    r'/wp-json/',
    r'/xmlrpc\.php',
    r'/feed/?$',
    r'\?replytocom=',
    r'/wp-comments-post\.php',
    
    # === WIX ===
    r'/_api/',
    r'/wix-code/',
    r'/_serverless/',
    
    # === GENERAL ===
    r'/cdn-cgi/',
    r'\?preview_theme_id=',
    r'\?cache=',
    r'/api/2\d+/',
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


def is_domain_blocked(domain):
    """Check if domain matches blocked list (exact or suffix match, never substring)"""
    domain_lower = domain.lower()
    for blocked in BLOCKED_DOMAINS:
        # Exact match: t.co == t.co
        if domain_lower == blocked:
            return True
        # Suffix match: analytics.t.co ends with .t.co
        if domain_lower.endswith('.' + blocked):
            return True
    # Prefix match: ads.example.com starts with ads.
    for prefix in BLOCKED_DOMAIN_PREFIXES:
        if domain_lower.startswith(prefix):
            return True
    return False


def is_domain_allowed(domain, filter_config):
    """Check if a domain is allowed based on filter config"""
    if is_domain_blocked(domain):
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
    
    # -k disabled: wget2 convert-links corrupts minified HTML
    # Links are converted by html_cleaner.py after download instead
    # if opts.get('convert_links', True):
    #     cmd.append('-k')
    
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
    
    # Build combined reject regex: blocked domains (with proper boundaries) + URL patterns
    reject_parts = []
    for d in BLOCKED_DOMAINS[:20]:
        # Escape dots for regex, match as domain in URL: ://domain/ or ://sub.domain/
        escaped = d.replace('.', r'\.')
        reject_parts.append(f'(://|\\.){escaped}(/|$)')
    for prefix in BLOCKED_DOMAIN_PREFIXES:
        escaped = prefix.replace('.', r'\.')
        reject_parts.append(f'://{escaped}')
    reject_parts.extend(BLOCKED_URL_PATHS)
    reject_parts.extend(REJECT_URL_PATTERNS)
    reject_regex = '|'.join(reject_parts)
    cmd.extend(['--reject-regex', reject_regex])
    
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
    
    for blocked in BLOCKED_DOMAINS:
        cmd.append(f'-*{blocked}/*')
        cmd.append(f'-*.{blocked}/*')
    for prefix in BLOCKED_DOMAIN_PREFIXES:
        cmd.append(f'-*://{prefix}*')
    
    # Platform-specific reject patterns (convert regex to httrack glob)
    httrack_rejects = [
        '*checkouts/*', '*.oembed*', '*/cdn/shopifycloud/*',
        '*/web-pixels-manager*', '*?variant=*',
        '*/cart.js*', '*/cart/add*', '*/cart/change*',
        '*/account/*', '*/policies/*',
        '*&width=*', '*?width=*', '*&w=*', '*?w=*',
        '*&size=*', '*?size=*', '*&resize=*', '*?resize=*',
        '*&fit=*', '*?fit=*', '*&quality=*', '*?quality=*',
        '*?format=auto*',
        '*/wp-admin/*', '*/wp-login.php*', '*/wp-json/*',
        '*/xmlrpc.php*', '*?replytocom=*', '*/wp-comments-post.php*',
        '*/_api/*', '*/wix-code/*', '*/_serverless/*',
        '*/cdn-cgi/*', '*?preview_theme_id=*', '*?cache=*',
    ]
    for pattern in httrack_rejects:
        cmd.append(f'-{pattern}')
    
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
    """Update job statistics from output - count only downloaded site content"""
    if not job.output_dir.exists():
        return
    
    EXCLUDE_DIRS = {'vue-app', '_wcloner', 'node_modules', 'hts-cache', '.git'}
    EXCLUDE_FILES = {'backend-server.js', 'preview.png'}
    
    try:
        count = 0
        total_bytes = 0
        for f in job.output_dir.rglob('*'):
            if not f.is_file():
                continue
            # Skip excluded directories
            parts = f.relative_to(job.output_dir).parts
            if any(p in EXCLUDE_DIRS for p in parts):
                continue
            # Skip excluded root-level files
            if len(parts) == 1 and parts[0] in EXCLUDE_FILES:
                continue
            count += 1
            total_bytes += f.stat().st_size
        
        job.files_downloaded = count
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


def cleanup_rejected_content(job):
    """Remove directories and files that match reject patterns (checkouts, shopifycloud, etc.)"""
    if not job.output_dir.exists():
        return
    
    # Directories to remove inside each domain folder
    rejected_dirs = [
        'checkouts', 'account', 'policies',
    ]
    # Subdirectories inside cdn/ to remove
    rejected_cdn_dirs = [
        'shopifycloud',
    ]
    # File patterns to remove
    rejected_file_patterns = [
        re.compile(r'\.oembed$'),
    ]
    
    removed_files = 0
    removed_dirs = 0
    freed_bytes = 0
    
    for domain_folder in job.output_dir.iterdir():
        if not domain_folder.is_dir() or domain_folder.name.startswith('_') or domain_folder.name in ('hts-cache', 'vue-app'):
            continue
        
        # Remove rejected directories
        for dirname in rejected_dirs:
            target = domain_folder / dirname
            if target.exists() and target.is_dir():
                try:
                    dir_size = sum(f.stat().st_size for f in target.rglob('*') if f.is_file())
                    shutil.rmtree(target)
                    removed_dirs += 1
                    freed_bytes += dir_size
                    job.output_lines.append(f"[Cleanup] Removed {domain_folder.name}/{dirname}")
                except Exception as e:
                    job.output_lines.append(f"[Cleanup] Error removing {dirname}: {e}")
        
        # Remove rejected cdn subdirectories
        cdn_dir = domain_folder / 'cdn'
        if cdn_dir.exists():
            for dirname in rejected_cdn_dirs:
                target = cdn_dir / dirname
                if target.exists() and target.is_dir():
                    try:
                        dir_size = sum(f.stat().st_size for f in target.rglob('*') if f.is_file())
                        shutil.rmtree(target)
                        removed_dirs += 1
                        freed_bytes += dir_size
                        job.output_lines.append(f"[Cleanup] Removed {domain_folder.name}/cdn/{dirname}")
                    except Exception as e:
                        job.output_lines.append(f"[Cleanup] Error removing cdn/{dirname}: {e}")
        
        # Remove rejected files
        for f in domain_folder.rglob('*'):
            if f.is_file():
                for pattern in rejected_file_patterns:
                    if pattern.search(f.name):
                        try:
                            freed_bytes += f.stat().st_size
                            f.unlink()
                            removed_files += 1
                        except:
                            pass
                        break
    
    if removed_dirs > 0 or removed_files > 0:
        from .utils import format_size
        job.output_lines.append(
            f"[Cleanup] Removed {removed_dirs} dirs, {removed_files} files, freed {format_size(freed_bytes)}"
        )


def cleanup_external_domains(job, pre_existing_dirs=None):
    """Remove folders of external domains and rejected content.
    
    Args:
        pre_existing_dirs: set of folder names that existed BEFORE download started.
                          These will NEVER be deleted to prevent losing previously downloaded content.
    """
    filter_config = get_domain_filter_config(job)
    
    if not job.output_dir.exists():
        return
    
    # Получаем основной домен сайта из landing.json
    site_main_domain = None
    landing_json = job.output_dir / '_wcloner' / 'landing.json'
    if landing_json.exists():
        try:
            import json
            with open(landing_json, 'r') as f:
                landing_data = json.load(f)
                site_main_domain = landing_data.get('domain')
        except:
            pass
    
    if pre_existing_dirs is None:
        pre_existing_dirs = set()
    
    removed_count = 0
    job.output_lines.append(f"[Cleanup] Main domain: {site_main_domain}, pre_existing: {pre_existing_dirs}")
    
    for folder in job.output_dir.iterdir():
        if not folder.is_dir():
            continue
        
        folder_name = folder.name
        
        if folder_name in ('hts-cache', 'hts-log.txt', 'cookies.txt', '_wcloner', 'vue-app', '_site'):
            continue
        
        # ВАЖНО: Никогда не удаляем папку основного домена сайта
        if site_main_domain and folder_name == site_main_domain:
            job.output_lines.append(f"[Cleanup] KEEP main domain: {folder_name}")
            continue
        
        # ВАЖНО: Никогда не удаляем папки, которые существовали до начала скачивания
        if folder_name in pre_existing_dirs:
            job.output_lines.append(f"[Cleanup] KEEP pre-existing: {folder_name}")
            continue
        
        if not is_domain_allowed(folder_name, filter_config):
            try:
                shutil.rmtree(folder)
                removed_count += 1
                job.output_lines.append(f"[Cleanup] Removed external: {folder_name}")
            except Exception as e:
                job.output_lines.append(f"[Cleanup] Error removing {folder_name}: {e}")
        else:
            job.output_lines.append(f"[Cleanup] KEEP allowed: {folder_name}")
    
    if removed_count > 0:
        job.output_lines.append(f"[Cleanup] Removed {removed_count} external domain folders")
    else:
        job.output_lines.append(f"[Cleanup] Nothing removed")
    
    # Also clean up rejected content inside allowed domains
    cleanup_rejected_content(job)


def run_wget_job(job_id):
    """Run download job in background (supports multiple engines)"""
    job = jobs.get(job_id)
    if not job:
        return
    
    job.status = 'running'
    job.started_at = datetime.now()
    
    # Запоминаем существующие папки ДО начала любого скачивания
    pre_existing_dirs = set()
    if job.output_dir.exists():
        for item in job.output_dir.iterdir():
            if item.is_dir():
                pre_existing_dirs.add(item.name)
    
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
        
        cleanup_external_domains(job, pre_existing_dirs)
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
        
        # Auto-generate preview screenshot
        if job.status == 'completed':
            # Convert links: since -k is disabled, we convert URLs ourselves
            try:
                from .html_cleaner import clean_downloaded_site
                parsed = urlparse(job.url)
                main_domain = parsed.netloc.replace('www.', '')
                job.output_lines.append("[WCLoner] Конвертация ссылок...")
                clean_stats = clean_downloaded_site(job.output_dir, main_domain)
                if clean_stats.get('error'):
                    job.output_lines.append(f"[WCLoner] Ошибка очистки: {clean_stats['error']}")
                else:
                    job.output_lines.append(
                        f"[WCLoner] Ссылки сконвертированы: {clean_stats.get('links_converted', 0)} ссылок "
                        f"в {clean_stats.get('modified_files', 0)} файлах"
                    )
            except Exception as e:
                job.output_lines.append(f"[WCLoner] Ошибка конвертации ссылок: {str(e)}")
            
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
            
            # Auto-generate Vue wrapper and backend server
            vue_dir = job.output_dir / 'vue-app'
            backend_file = job.output_dir / 'backend-server.js'
            if vue_dir.exists() and (vue_dir / 'package.json').exists() and backend_file.exists():
                job.output_lines.append("[WCLoner] Vue обёртка и Node.js сервер уже существуют")
            else:
                try:
                    from .file_manager import generate_vue_wrapper
                    parsed = urlparse(job.url)
                    main_domain = parsed.netloc.replace('www.', '')
                    
                    job.output_lines.append("[WCLoner] Генерация Vue обёртки и Node.js сервера...")
                    success = generate_vue_wrapper(job.output_dir, main_domain, 3000, 3001)
                    
                    if success:
                        job.output_lines.append("[WCLoner] ✅ Vue обёртка и Node.js сервер созданы")
                    else:
                        job.output_lines.append("[WCLoner] ⚠ Не удалось создать Vue обёртку")
                except Exception as e:
                    job.output_lines.append(f"[WCLoner] ❌ Ошибка генерации скриптов: {str(e)}")
        
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
    
    # Запоминаем существующие папки ДО скачивания, чтобы cleanup не удалил их
    pre_existing_dirs = set()
    if job.output_dir.exists():
        for item in job.output_dir.iterdir():
            if item.is_dir():
                pre_existing_dirs.add(item.name)
    
    # Create log file for output
    log_dir = job.output_dir / '_wcloner'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'wget_{job.id}.log'
    
    # Start subprocess with shell redirect to avoid buffer issues
    try:
        # Use shell to redirect output to file
        # Quote ALL arguments to prevent shell interpretation of |, ?, (, ), *, $ etc.
        cmd_str = ' '.join(shlex.quote(c) for c in cmd)
        shell_cmd = f'{cmd_str} > "{log_file}" 2>&1'
        
        # DEBUG: save exact shell command for troubleshooting
        debug_cmd_file = log_dir / f'debug_cmd_{job.id}.sh'
        with open(debug_cmd_file, 'w') as df:
            df.write(f'#!/bin/sh\n{shell_cmd}\n')
        
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
            
            cleanup_external_domains(job, pre_existing_dirs)
            update_job_stats(job)
            
            job.output_lines.append(f"[Process] Files found: {job.files_downloaded}")
            
            # wget2 exit codes: 0=success, 4=network error, 8=server error (403/404)
            # Partial success: if files were downloaded, consider completed
            if job.stop_requested:
                job.status = 'stopped'
            elif returncode == 0 or job.files_downloaded > 0:
                job.status = 'completed'
                if returncode != 0:
                    job.output_lines.append(f"[Process] Partial success: exit code {returncode} but {job.files_downloaded} files downloaded")
            else:
                job.status = 'failed'
            job.finished_at = datetime.now()
            
            # Auto-generate preview
            if job.status == 'completed':
                # NOTE: Автоматическая очистка HTML отключена - может повредить верстку.
                # Используйте таб "Трекеры" для просмотра найденных трекеров.
                
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
                
                # Auto-generate Vue wrapper and backend server
                vue_dir = job.output_dir / 'vue-app'
                backend_file = job.output_dir / 'backend-server.js'
                if vue_dir.exists() and (vue_dir / 'package.json').exists() and backend_file.exists():
                    job.output_lines.append("[WCLoner] Vue обёртка и Node.js сервер уже существуют")
                else:
                    try:
                        from .file_manager import generate_vue_wrapper
                        parsed = urlparse(job.url)
                        main_domain = parsed.netloc.replace('www.', '')
                        
                        job.output_lines.append("[WCLoner] Генерация Vue обёртки и Node.js сервера...")
                        success = generate_vue_wrapper(job.output_dir, main_domain, 3000, 3001)
                        
                        if success:
                            job.output_lines.append("[WCLoner] ✅ Vue обёртка и Node.js сервер созданы")
                        else:
                            job.output_lines.append("[WCLoner] ⚠ Не удалось создать Vue обёртку")
                    except Exception as e:
                        job.output_lines.append(f"[WCLoner] ❌ Ошибка генерации скриптов: {e}")
            
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
