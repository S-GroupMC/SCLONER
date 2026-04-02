"""
Configuration module - paths, constants, job storage
"""
import os
import json
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
WGET2_PATH = str(BASE_DIR / 'bin' / 'wget2')
HTTRACK_PATH = str(BASE_DIR / 'bin' / 'httrack')
LIB_DIR = str(BASE_DIR / 'lib')
PUPPETEER_SCRIPT = BASE_DIR / 'admin' / 'puppeteer-crawler.js'
DOWNLOADS_DIR = BASE_DIR / 'downloads'
PREVIEWS_DIR = BASE_DIR / 'admin' / 'static' / 'previews'
JOBS_FILE = BASE_DIR / 'admin' / 'jobs.json'
LANDINGS_CONFIG_FILE = BASE_DIR / 'admin' / 'landings.json'

# Environment for running wget2/httrack with local libraries
TOOL_ENV = os.environ.copy()
TOOL_ENV['DYLD_LIBRARY_PATH'] = LIB_DIR

# Ensure directories exist
DOWNLOADS_DIR.mkdir(exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

# Store active jobs
jobs = {}

# Store for active scans
active_scans = {}

# Store for running servers
running_servers = {}


def save_jobs():
    """Save jobs to JSON file for persistence"""
    from .downloader import WgetJob
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
            'output_lines': job.output_lines[-100:],
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'finished_at': job.finished_at.isoformat() if job.finished_at else None,
            'folder_name': job.folder_name,
            'pre_file_count': getattr(job, 'pre_file_count', 0)
        }
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs_data, f, indent=2)
    except Exception as e:
        print(f"Error saving jobs: {e}")


def load_jobs():
    """Load jobs from JSON file on startup"""
    from .downloader import WgetJob
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
                data.get('options', {}),
                data.get('use_wget2', True),
                data.get('folder_name', ''),
                data.get('engine', 'wget2')
            )
            job.status = data.get('status', 'unknown')
            job.files_downloaded = data.get('files_downloaded', 0)
            job.total_size = data.get('total_size', 0)
            job.output_lines = data.get('output_lines', [])
            job.pre_file_count = data.get('pre_file_count', 0)
            if data.get('started_at'):
                job.started_at = datetime.fromisoformat(data['started_at'])
            if data.get('finished_at'):
                job.finished_at = datetime.fromisoformat(data['finished_at'])
            jobs[job_id] = job
    except Exception as e:
        print(f"Error loading jobs: {e}")


def load_landings_config():
    """Load landings configuration"""
    if not LANDINGS_CONFIG_FILE.exists():
        return {}
    try:
        with open(LANDINGS_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_landings_config(config):
    """Save landings configuration"""
    try:
        with open(LANDINGS_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving landings config: {e}")
