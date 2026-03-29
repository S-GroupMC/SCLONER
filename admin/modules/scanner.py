"""
Site Scanner & Fixer module — finds and fixes broken links, missing files,
truncated downloads, hardcoded absolute URLs, and other common issues
in downloaded (cloned) websites.

Supports pause/stop/progress reporting for the frontend UI.

Issue categories:
  BROKEN_LINK      — href/src points to a local file that doesn't exist
  EMPTY_FILE       — 0-byte file (failed download)
  TRUNCATED_HTML   — HTML file missing closing </html> or </body>
  ABSOLUTE_URL     — hardcoded absolute URL that should be relative
  MISSING_RESOURCE — resource referenced in CSS/JS but not downloaded
  REDIRECT_STUB    — tiny HTML file that is just a meta-refresh redirect

Fix actions:
  - Download missing files from the origin server
  - Rewrite absolute URLs to relative paths
  - Re-download truncated / empty files
  - Remove dead references
"""

import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote

from urllib.request import urlopen, Request as UrlRequest
from urllib.error import URLError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global registry of running scans  { scan_id: ScanTask }
# ---------------------------------------------------------------------------
_active_scans: dict = {}

SKIP_DIRS = {'vue-app', 'node_modules', '_wcloner', '.git', '_site',
             '__pycache__', 'api-cache', '.vite'}

BINARY_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico', '.svg',
               '.woff', '.woff2', '.ttf', '.eot', '.otf',
               '.mp4', '.webm', '.mp3', '.ogg', '.wav',
               '.zip', '.gz', '.br', '.pdf', '.map'}

HTML_EXTS = {'.html', '.htm'}
CSS_EXTS = {'.css'}
JS_EXTS = {'.js', '.mjs'}
TEXT_EXTS = HTML_EXTS | CSS_EXTS | JS_EXTS


def _should_skip(path: Path) -> bool:
    parts = path.parts
    return any(p in SKIP_DIRS for p in parts)


def _detect_domains(folder: Path) -> list[str]:
    """Return list of domain-directory names inside *folder*."""
    domains = []
    for d in folder.iterdir():
        if d.is_dir() and '.' in d.name and d.name not in SKIP_DIRS:
            domains.append(d.name)
    return domains


def _resolve_link(link: str, file_path: Path, domain_dir: Path) -> str | None:
    """Resolve a relative/absolute link to a path relative to *domain_dir*.
    Returns None if the link is external or data/JS/mailto."""
    if not link or link.startswith(('http://', 'https://', '//', 'data:',
                                     'javascript:', 'mailto:', '#', '{')):
        return None

    link = link.split('?')[0].split('#')[0]
    if not link:
        return None

    link = unquote(link)

    if link.startswith('/'):
        resolved = domain_dir / link.lstrip('/')
    else:
        resolved = file_path.parent / link

    try:
        return str(resolved.resolve().relative_to(domain_dir.resolve()))
    except (ValueError, OSError):
        return None


# =========================================================================
# ScanTask — runs in a background thread, supports pause / stop
# =========================================================================

class ScanTask:
    """Background scan task with progress, pause & stop support."""

    def __init__(self, folder_path: str | Path, scan_id: str | None = None):
        self.folder = Path(folder_path)
        self.scan_id = scan_id or str(uuid.uuid4())[:8]
        # state
        self.status = 'pending'          # pending | scanning | paused | fixing | done | stopped | error
        self.phase = ''                  # current phase label
        self.progress = 0                # 0..100
        self.total_files = 0
        self.scanned_files = 0
        self.issues: list[dict] = []
        self.fixed: list[dict] = []
        self.error_msg = ''
        self.started_at = 0.0
        self.finished_at = 0.0
        # control
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()                # not paused initially
        self._thread: threading.Thread | None = None
        self._domains: list[str] = []

    # -- control --------------------------------------------------------
    def start(self):
        self.status = 'scanning'
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        if self.status == 'scanning':
            self._pause.clear()
            self.status = 'paused'

    def resume(self):
        if self.status == 'paused':
            self._pause.set()
            self.status = 'scanning'

    def stop(self):
        self._stop.set()
        self._pause.set()          # unblock if paused
        self.status = 'stopped'

    # -- helpers --------------------------------------------------------
    def _check(self):
        """Call periodically — respects pause & stop."""
        if self._stop.is_set():
            raise _Stopped()
        self._pause.wait()

    def _set_progress(self, scanned: int, total: int, phase: str = ''):
        self.scanned_files = scanned
        self.total_files = total
        self.progress = int(scanned / total * 100) if total else 0
        if phase:
            self.phase = phase

    def to_dict(self) -> dict:
        elapsed = (self.finished_at or time.time()) - self.started_at if self.started_at else 0
        return {
            'scan_id': self.scan_id,
            'status': self.status,
            'phase': self.phase,
            'progress': self.progress,
            'total_files': self.total_files,
            'scanned_files': self.scanned_files,
            'issues_count': len(self.issues),
            'fixed_count': len(self.fixed),
            'issues': self.issues,
            'fixed': self.fixed,
            'error': self.error_msg,
            'elapsed': round(elapsed, 1),
            'categories': self._categorise(),
        }

    def _categorise(self) -> dict:
        cats: dict[str, int] = {}
        for iss in self.issues:
            cat = iss.get('category', 'OTHER')
            cats[cat] = cats.get(cat, 0) + 1
        return cats

    # -- main scan logic ------------------------------------------------
    def _run(self):
        try:
            self._domains = _detect_domains(self.folder)
            all_files = self._collect_files()
            self.total_files = len(all_files)
            self._set_progress(0, self.total_files, 'Сканирование файлов')

            for idx, fpath in enumerate(all_files):
                self._check()
                self._scan_file(fpath)
                self._set_progress(idx + 1, self.total_files)

            self.status = 'done'
        except _Stopped:
            self.status = 'stopped'
        except Exception as e:
            logger.exception('Scanner error')
            self.error_msg = str(e)
            self.status = 'error'
        finally:
            self.finished_at = time.time()
            self.progress = 100 if self.status == 'done' else self.progress

    def _collect_files(self) -> list[Path]:
        """Collect all scannable files inside domain dirs."""
        files = []
        for domain in self._domains:
            domain_dir = self.folder / domain
            for f in domain_dir.rglob('*'):
                if f.is_file() and not _should_skip(f.relative_to(self.folder)):
                    files.append(f)
        return sorted(files)

    def _domain_dir_for(self, fpath: Path) -> Path | None:
        for domain in self._domains:
            dd = self.folder / domain
            try:
                fpath.relative_to(dd)
                return dd
            except ValueError:
                continue
        return None

    def _scan_file(self, fpath: Path):
        ext = fpath.suffix.lower()
        size = fpath.stat().st_size
        rel = str(fpath.relative_to(self.folder))
        domain_dir = self._domain_dir_for(fpath)

        # 1) Empty file
        if size == 0:
            self.issues.append({
                'category': 'EMPTY_FILE',
                'file': rel,
                'detail': 'Файл пустой (0 байт)',
                'fixable': True,
            })
            return  # no point scanning content

        # 2) Suspiciously small binary
        if ext in BINARY_EXTS and size < 20:
            self.issues.append({
                'category': 'EMPTY_FILE',
                'file': rel,
                'detail': f'Файл слишком маленький ({size} байт)',
                'fixable': True,
            })
            return

        if ext not in TEXT_EXTS:
            return  # nothing more to check for non-text

        # --- read text content ---
        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        # 3) Truncated HTML
        if ext in HTML_EXTS:
            lower = content.lower()
            if '<html' in lower and '</html>' not in lower and len(content) > 200:
                self.issues.append({
                    'category': 'TRUNCATED_HTML',
                    'file': rel,
                    'detail': 'Отсутствует закрывающий </html>',
                    'fixable': True,
                })
            # Redirect stub (tiny file with meta refresh or JS redirect)
            if len(content) < 512 and ('http-equiv="refresh"' in lower or
                                        'window.location' in lower or
                                        'location.replace' in lower or
                                        'location.href' in lower):
                self.issues.append({
                    'category': 'REDIRECT_STUB',
                    'file': rel,
                    'detail': 'HTML-файл является редиректом',
                    'fixable': False,
                })

        # 4) Broken internal links (HTML only)
        if ext in HTML_EXTS and domain_dir:
            self._check_links(content, fpath, domain_dir, rel)

        # 5) Hardcoded absolute URLs pointing to own domain (skip external CSS/font dirs)
        if domain_dir and domain_dir.name in self._domains[:1]:
            domain_name = domain_dir.name
            self._check_absolute_urls(content, domain_name, rel)

        # 6) CSS url() references (only for main domain files)
        if ext in CSS_EXTS and domain_dir and domain_dir.name in self._domains[:1]:
            self._check_css_urls(content, fpath, domain_dir, rel)

    # -- sub-scanners ---------------------------------------------------

    def _check_links(self, content: str, fpath: Path, domain_dir: Path, rel: str):
        """Find href/src that point to missing local files."""
        links = re.findall(r'(?:href|src|srcset)=["\']([^"\']+)["\']', content)
        seen = set()
        for raw_link in links:
            # srcset may have multiple entries
            for link_part in raw_link.split(','):
                link = link_part.strip().split()[0] if link_part.strip() else ''
                if not link:
                    continue
                resolved = _resolve_link(link, fpath, domain_dir)
                if resolved is None or resolved in seen:
                    continue
                seen.add(resolved)
                target = domain_dir / resolved
                if not target.exists() and not (target.with_suffix('.html')).exists():
                    # skip _next/data or api paths — they are dynamic
                    if any(p in resolved for p in ('_next/data', '/api/', '__next')):
                        continue
                    self.issues.append({
                        'category': 'BROKEN_LINK',
                        'file': rel,
                        'detail': f'Ссылка на отсутствующий файл: {link}',
                        'missing': resolved,
                        'fixable': True,
                    })

    def _check_absolute_urls(self, content: str, domain: str, rel: str):
        """Find hardcoded https://domain/... URLs in text files."""
        escaped = re.escape(domain)
        pattern = re.compile(r'https?://' + escaped + r'(/[^\s"\'<>)*}\]]*)?')
        matches = pattern.findall(content)
        if matches:
            count = len(set(matches))
            self.issues.append({
                'category': 'ABSOLUTE_URL',
                'file': rel,
                'detail': f'{count} абсолютных URL для {domain}',
                'count': count,
                'fixable': True,
            })

    def _check_css_urls(self, content: str, fpath: Path, domain_dir: Path, rel: str):
        """Find url(...) in CSS that reference missing local files."""
        urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', content)
        seen = set()
        for u in urls:
            if u.startswith(('data:', 'http://', 'https://', '//')):
                continue
            resolved = _resolve_link(u, fpath, domain_dir)
            if resolved is None or resolved in seen:
                continue
            seen.add(resolved)
            target = domain_dir / resolved
            if not target.exists():
                self.issues.append({
                    'category': 'MISSING_RESOURCE',
                    'file': rel,
                    'detail': f'CSS url() → отсутствует: {u}',
                    'missing': resolved,
                    'fixable': True,
                })

    # =================================================================
    # Fix logic
    # =================================================================

    def start_fix(self, categories: list[str] | None = None):
        """Fix issues in the foreground (blocking). Returns fixed list."""
        if self.status not in ('done', 'stopped'):
            return
        self.status = 'fixing'
        self.phase = 'Исправление'
        self.fixed = []
        try:
            self._do_fix(categories)
        except Exception as e:
            logger.exception('Fix error')
            self.error_msg = str(e)
        finally:
            self.status = 'done'
            self.finished_at = time.time()

    def _do_fix(self, categories: list[str] | None):
        issues_to_fix = [i for i in self.issues if i.get('fixable')]
        if categories:
            issues_to_fix = [i for i in issues_to_fix if i['category'] in categories]

        base_url = self._guess_base_url()

        for idx, issue in enumerate(issues_to_fix):
            self._set_progress(idx + 1, len(issues_to_fix), 'Исправление')
            cat = issue['category']
            try:
                if cat == 'EMPTY_FILE':
                    ok = self._fix_download(issue, base_url)
                elif cat == 'TRUNCATED_HTML':
                    ok = self._fix_download(issue, base_url)
                elif cat == 'BROKEN_LINK':
                    ok = self._fix_download_missing(issue, base_url)
                elif cat == 'MISSING_RESOURCE':
                    ok = self._fix_download_missing(issue, base_url)
                elif cat == 'ABSOLUTE_URL':
                    ok = self._fix_absolute_url(issue)
                else:
                    ok = False

                if ok:
                    self.fixed.append({**issue, 'fix_status': 'ok'})
                else:
                    self.fixed.append({**issue, 'fix_status': 'skipped'})
            except Exception as e:
                self.fixed.append({**issue, 'fix_status': 'error', 'fix_error': str(e)})

    def _guess_base_url(self) -> str:
        meta_path = self.folder / '_wcloner' / 'landing.json'
        if meta_path.exists():
            import json
            try:
                meta = json.loads(meta_path.read_text())
                return meta.get('url', f'https://{self._domains[0]}')
            except Exception:
                pass
        if self._domains:
            return f'https://{self._domains[0]}'
        return ''

    def _fix_download(self, issue: dict, base_url: str) -> bool:
        """Re-download a broken/empty/truncated file from the origin."""
        rel = issue['file']
        # rel is like "ibighit.com/ko/main/index.html"
        parts = rel.split('/', 1)
        if len(parts) < 2:
            return False
        domain, path = parts[0], parts[1]
        url = f'https://{domain}/{path}'

        target = self.folder / rel
        return self._download_file(url, target)

    def _fix_download_missing(self, issue: dict, base_url: str) -> bool:
        """Download a missing file referenced by another file."""
        missing = issue.get('missing', '')
        if not missing:
            return False
        # figure out which domain dir
        file_rel = issue['file']
        parts = file_rel.split('/', 1)
        if not parts:
            return False
        domain = parts[0]
        url = f'https://{domain}/{missing}'
        target = self.folder / domain / missing
        return self._download_file(url, target)

    def _download_file(self, url: str, target: Path) -> bool:
        """Download a single file from URL to target path."""
        try:
            req = UrlRequest(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            })
            resp = urlopen(req, timeout=15)
            if resp.status != 200:
                return False
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'wb') as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            return True
        except Exception as e:
            logger.debug(f'Download failed {url}: {e}')
            return False

    def _fix_absolute_url(self, issue: dict) -> bool:
        """Rewrite hardcoded absolute URLs to relative in a text file."""
        fpath = self.folder / issue['file']
        if not fpath.exists():
            return False
        domain_dir = self._domain_dir_for(fpath)
        if not domain_dir:
            return False
        domain = domain_dir.name
        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
            escaped = re.escape(domain)
            new_content = re.sub(r'https?://' + escaped, '', content)
            if new_content != content:
                fpath.write_text(new_content, encoding='utf-8')
                return True
        except Exception as e:
            logger.debug(f'Fix absolute URL failed {fpath}: {e}')
        return False


class _Stopped(Exception):
    pass


# =========================================================================
# Public API for app.py
# =========================================================================

def start_scan(folder_path: str | Path) -> ScanTask:
    """Create and start a background scan. Returns the ScanTask."""
    task = ScanTask(folder_path)
    _active_scans[task.scan_id] = task
    task.start()
    return task


def get_scan(scan_id: str) -> ScanTask | None:
    return _active_scans.get(scan_id)


def get_latest_scan(folder_path: str | Path) -> ScanTask | None:
    """Return the most recent scan for a given folder."""
    folder_str = str(Path(folder_path).resolve())
    latest = None
    for task in _active_scans.values():
        if str(task.folder.resolve()) == folder_str:
            if latest is None or task.started_at > latest.started_at:
                latest = task
    return latest


def fix_issues(scan_id: str, categories: list[str] | None = None) -> dict:
    """Run fix on a completed scan. Returns the task dict."""
    task = _active_scans.get(scan_id)
    if not task:
        return {'error': 'Scan not found'}
    if task.status not in ('done', 'stopped'):
        return {'error': f'Cannot fix — scan status is {task.status}'}
    task.start_fix(categories)
    return task.to_dict()
