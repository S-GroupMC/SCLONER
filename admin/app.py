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
WGET2_PATH = os.environ.get('WGET2_PATH', str(BASE_DIR / 'bin' / 'wget2'))
HTTRACK_PATH = os.environ.get('HTTRACK_PATH', '/opt/homebrew/bin/httrack')
PUPPETEER_SCRIPT = BASE_DIR / 'admin' / 'puppeteer-crawler.js'
DOWNLOADS_DIR = BASE_DIR / 'downloads'
DOWNLOADS_DIR.mkdir(exist_ok=True)
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
            'engine': self.engine
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
        rel_path = index_file.relative_to(DOWNLOADS_DIR)
        return jsonify({'path': str(rel_path)})
    
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


@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'ok'})


if __name__ == '__main__':
    print(f"Wget Admin starting...")
    print(f"Using wget2: {WGET2_PATH}")
    print(f"Downloads dir: {DOWNLOADS_DIR}")
    load_jobs()  # Load saved jobs on startup
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)
