"""
Site Scanner & Fixer v2 — умный анализ скачанных сайтов.

Фазы сканирования:
  1. Целостность файлов    — пустые, обрезанные, битые
  2. Анализ путей/ссылок   — ../domain/ ссылки от wget2, сломанные пути
  3. Внешние ресурсы       — нескачанные домены (CDN, картинки)
  4. JS/CSS чанки          — целостность бандлов (_nuxt, _next, chunks)
  5. Сравнение с оригиналом — сверка ссылок с живым сайтом

Категории проблем:
  EMPTY_FILE       — файл 0 байт или слишком маленький
  TRUNCATED_HTML   — HTML без закрывающего </html>
  REDIRECT_STUB    — HTML-заглушка (meta-refresh / JS-redirect)
  BROKEN_LINK      — href/src ведёт на несуществующий локальный файл
  ABSOLUTE_URL     — захардкоженный абсолютный URL своего домена
  MISSING_RESOURCE — CSS url() на отсутствующий файл
  WRONG_PATH       — ../domain/path ссылка (ломается на локальном сервере)
  MISSING_EXTERNAL — ресурс с нескачанного внешнего домена
  BROKEN_CHUNK     — JS/CSS бандл пустой, обрезанный или битый
  ORIGIN_MISMATCH  — ссылка с оригинала отсутствует в локальной копии
  ENCODED_PATH     — URL-encoded путь (%2F вместо /) — может не работать
  DUPLICATE_LANG   — дублирование языкового префикса (/ko/ko/, /en/en/)

Исправления:
  - Перезапись ../domain/path → /domain/path (скачанные) или https://domain/path
  - Докачка отсутствующих файлов с оригинала
  - Перезапись абсолютных URL на относительные
  - Перекачка пустых/обрезанных файлов
"""

import json
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
# Глобальный реестр сканов  { scan_id: ScanTask }
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

# Паттерн: ../domain.name/path  (ссылки от wget2)
# Ловит href="../domain/path", src='../domain/path', url(../domain/path)
_DOTDOT_DOMAIN_RE = re.compile(
    r'(?:href|src|srcset)=["\'](\.\./([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})/([^"\'>\s]*))["\']'
    r'|'
    r'url\(["\']?(\.\./([a-zA-Z0-9._-]+\.[a-zA-Z]{2,})/([^"\')\s]*))["\']?\)',
)

# Паттерн: все href/src значения
_ATTR_RE = re.compile(r'(?:href|src|srcset)=["\']([^"\']+)["\']')


def _should_skip(path: Path) -> bool:
    parts = path.parts
    return any(p in SKIP_DIRS for p in parts)


def _detect_domains(folder: Path) -> list[str]:
    """Вернуть список доменных папок внутри *folder*."""
    domains = []
    for d in folder.iterdir():
        if d.is_dir() and '.' in d.name and d.name not in SKIP_DIRS:
            domains.append(d.name)
    return sorted(domains)


def _resolve_link(link: str, file_path: Path, domain_dir: Path) -> str | None:
    """Разрешить относительную/абсолютную ссылку в путь относительно *domain_dir*.
    None если внешняя или спец-ссылка."""
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


def _guess_main_domain(domains: list[str]) -> str:
    """Определить основной домен (без www, без CDN)."""
    for d in domains:
        if not any(cdn in d for cdn in ('cdn.', 'fonts.', 'typekit', 'cloudflare',
                                         'jsdelivr', 'gstatic', 'fontawesome')):
            if d.startswith('www.'):
                continue
            return d
    return domains[0] if domains else ''


# =========================================================================
# ScanTask — фоновое сканирование с паузой / стопом
# =========================================================================

class ScanTask:
    """Фоновая задача сканирования с прогрессом, паузой и стопом."""

    def __init__(self, folder_path: str | Path, scan_id: str | None = None):
        self.folder = Path(folder_path)
        self.scan_id = scan_id or str(uuid.uuid4())[:8]
        # состояние
        self.status = 'pending'
        self.phase = ''
        self.progress = 0
        self.total_files = 0
        self.scanned_files = 0
        self.issues: list[dict] = []
        self.fixed: list[dict] = []
        self.error_msg = ''
        self.started_at = 0.0
        self.finished_at = 0.0
        # управление
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._pause.set()
        self._thread: threading.Thread | None = None
        self._domains: list[str] = []
        self._domain_set: set[str] = set()
        self._main_domain: str = ''

    # -- управление -----------------------------------------------------
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
        self._pause.set()
        self.status = 'stopped'

    def _check(self):
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

    # ===================================================================
    # Главный цикл — 5 фаз
    # ===================================================================

    def _run(self):
        try:
            self._domains = _detect_domains(self.folder)
            self._domain_set = set(self._domains)
            self._main_domain = _guess_main_domain(self._domains)

            all_files = self._collect_files()
            total_steps = len(all_files)
            step = 0

            # ── Фаза 1: Целостность файлов ──────────────────────────
            self._set_progress(0, total_steps, '① Целостность файлов')
            for idx, fpath in enumerate(all_files):
                self._check()
                self._scan_file_integrity(fpath)
                step += 1
                self._set_progress(step, total_steps + 3)

            # ── Фаза 2: Анализ путей и ссылок ───────────────────────
            html_files = [f for f in all_files if f.suffix.lower() in HTML_EXTS]
            self._set_progress(step, total_steps + 3, '② Анализ ссылок')
            for fpath in html_files:
                self._check()
                self._scan_links_smart(fpath)

            # ── Фаза 3: Внешние ресурсы (нескачанные домены) ────────
            self._set_progress(step + 1, total_steps + 3, '③ Внешние ресурсы')
            self._check()
            self._scan_external_assets(html_files)

            # ── Фаза 4: JS/CSS чанки ────────────────────────────────
            self._set_progress(step + 2, total_steps + 3, '④ JS/CSS чанки')
            self._check()
            self._scan_chunks(all_files)

            # ── Фаза 5: Сравнение с оригиналом ──────────────────────
            self._set_progress(step + 3, total_steps + 3, '⑤ Сравнение с оригиналом')
            self._check()
            self._compare_with_origin(html_files)

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

    # ===================================================================
    # Фаза 1 — целостность файлов
    # ===================================================================

    def _scan_file_integrity(self, fpath: Path):
        ext = fpath.suffix.lower()
        size = fpath.stat().st_size
        rel = str(fpath.relative_to(self.folder))

        # Пустой файл
        if size == 0:
            self.issues.append({
                'category': 'EMPTY_FILE', 'file': rel,
                'detail': 'Файл пустой (0 байт)', 'fixable': True,
            })
            return

        # Подозрительно маленький бинарник
        if ext in BINARY_EXTS and size < 20:
            self.issues.append({
                'category': 'EMPTY_FILE', 'file': rel,
                'detail': f'Файл слишком маленький ({size} байт)', 'fixable': True,
            })
            return

        if ext not in TEXT_EXTS:
            return

        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        # Обрезанный HTML
        if ext in HTML_EXTS:
            lower = content.lower()
            if '<html' in lower and '</html>' not in lower and len(content) > 200:
                self.issues.append({
                    'category': 'TRUNCATED_HTML', 'file': rel,
                    'detail': 'Отсутствует закрывающий </html>', 'fixable': True,
                })
            if len(content) < 512 and ('http-equiv="refresh"' in lower or
                                        'window.location' in lower or
                                        'location.replace' in lower or
                                        'location.href' in lower):
                self.issues.append({
                    'category': 'REDIRECT_STUB', 'file': rel,
                    'detail': 'HTML-файл является редиректом', 'fixable': False,
                })

        # Абсолютные URL основного домена
        if self._main_domain:
            domain_dir = self._domain_dir_for(fpath)
            if domain_dir and domain_dir.name == self._main_domain:
                self._check_absolute_urls(content, self._main_domain, rel)

        # CSS url() на отсутствующие файлы (только основной домен)
        if ext in CSS_EXTS:
            domain_dir = self._domain_dir_for(fpath)
            if domain_dir and domain_dir.name == self._main_domain:
                self._check_css_urls(content, fpath, domain_dir, rel)

    # ===================================================================
    # Фаза 2 — умный анализ ссылок
    # ===================================================================

    def _scan_links_smart(self, fpath: Path):
        """Анализ всех ссылок в HTML: ../domain/, сломанные, внутренние."""
        ext = fpath.suffix.lower()
        if ext not in HTML_EXTS:
            return
        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        rel = str(fpath.relative_to(self.folder))
        domain_dir = self._domain_dir_for(fpath)
        if not domain_dir:
            return

        # 2a) Найти ../domain/path ссылки (wget2 путаница)
        self._check_dotdot_links(content, fpath, rel)

        # 2b) Обычные сломанные ссылки (href/src на несуществующие файлы)
        self._check_broken_links(content, fpath, domain_dir, rel)
        
        # 2c) URL-encoded пути (%2F вместо /)
        self._check_encoded_paths(content, fpath, rel)
        
        # 2d) Дублирование языкового префикса (/ko/ko/, /en/en/)
        self._check_duplicate_lang_prefix(content, fpath, rel)

    def _check_dotdot_links(self, content: str, fpath: Path, rel: str):
        """Найти ../domain/path ссылки от wget2 — ломаются на локальном сервере."""
        seen = set()
        for m in _DOTDOT_DOMAIN_RE.finditer(content):
            # href/src: groups 2,3;  url(): groups 5,6
            domain = m.group(2) or m.group(5)
            path = m.group(3) or m.group(6) or ''
            if not domain:
                continue
            key = f'{domain}/{path}'
            if key in seen:
                continue
            seen.add(key)

            local_exists = (self.folder / domain).is_dir()
            file_exists = (self.folder / domain / path).exists() if local_exists else False

            self.issues.append({
                'category': 'WRONG_PATH',
                'file': rel,
                'detail': f'../{domain}/{path}' + (' (домен скачан)' if local_exists else ' (домен НЕ скачан)'),
                'domain': domain,
                'path': path,
                'local_exists': local_exists,
                'file_exists': file_exists,
                'fixable': True,
            })

    def _check_broken_links(self, content: str, fpath: Path, domain_dir: Path, rel: str):
        """href/src на несуществующие локальные файлы."""
        seen = set()
        for raw_link in _ATTR_RE.findall(content):
            for link_part in raw_link.split(','):
                link = link_part.strip().split()[0] if link_part.strip() else ''
                if not link or link.startswith('../'):
                    continue

                # /other-domain/path — кросс-доменная ссылка, проверяем в корне проекта
                if link.startswith('/'):
                    clean = link.split('?')[0].split('#')[0].lstrip('/')
                    first_seg = clean.split('/')[0] if clean else ''
                    if first_seg in self._domain_set:
                        target = self.folder / clean
                        if target.exists() or target.with_suffix('.html').exists():
                            continue
                        # Файл может быть index.html в подпапке
                        idx_path = target / 'index.html'
                        if idx_path.exists():
                            continue

                resolved = _resolve_link(link, fpath, domain_dir)
                if resolved is None or resolved in seen:
                    continue
                seen.add(resolved)
                target = domain_dir / resolved
                if not target.exists() and not target.with_suffix('.html').exists():
                    if any(p in resolved for p in ('_next/data', '/api/', '__next',
                                                    '_nuxt/builds', '.json')):
                        continue
                    self.issues.append({
                        'category': 'BROKEN_LINK', 'file': rel,
                        'detail': f'Ссылка на отсутствующий файл: {link}',
                        'missing': resolved, 'fixable': True,
                    })

    def _check_encoded_paths(self, content: str, fpath: Path, rel: str):
        """Найти URL-encoded пути (%2F вместо /) — могут не работать."""
        # Ищем src/href с %2F (encoded slash)
        pattern = re.compile(r'(?:href|src)=["\']([^"\']*%2[fF][^"\']*)["\']')
        seen = set()
        for m in pattern.finditer(content):
            encoded_path = m.group(1)
            if encoded_path in seen:
                continue
            seen.add(encoded_path)
            try:
                decoded = unquote(encoded_path)
            except Exception:
                decoded = encoded_path
            self.issues.append({
                'category': 'ENCODED_PATH', 'file': rel,
                'detail': f'URL-encoded путь: {encoded_path[:80]}...' if len(encoded_path) > 80 else f'URL-encoded путь: {encoded_path}',
                'encoded': encoded_path,
                'decoded': decoded,
                'fixable': True,
            })

    def _check_duplicate_lang_prefix(self, content: str, fpath: Path, rel: str):
        """Найти дублирование языкового префикса (/ko/ko/, /en/en/)."""
        # Ищем href с дублированием типа /ko/ko/, /en/en/, /ja/ja/
        pattern = re.compile(r'href=["\']\/([a-z]{2})\/\1\/([^"\']*)["\']')
        seen = set()
        for m in pattern.finditer(content):
            lang = m.group(1)
            path = m.group(2)
            key = f'/{lang}/{lang}/{path}'
            if key in seen:
                continue
            seen.add(key)
            correct = f'/{lang}/{path}'
            self.issues.append({
                'category': 'DUPLICATE_LANG', 'file': rel,
                'detail': f'Дублирование языка: /{lang}/{lang}/{path} → {correct}',
                'wrong': key,
                'correct': correct,
                'fixable': True,
            })

    def _check_absolute_urls(self, content: str, domain: str, rel: str):
        escaped = re.escape(domain)
        pattern = re.compile(r'https?://' + escaped + r'(/[^\s"\'<>)*}\]]*)?')
        matches = pattern.findall(content)
        if matches:
            count = len(set(matches))
            self.issues.append({
                'category': 'ABSOLUTE_URL', 'file': rel,
                'detail': f'{count} абсолютных URL для {domain}',
                'count': count, 'fixable': True,
            })

    def _check_css_urls(self, content: str, fpath: Path, domain_dir: Path, rel: str):
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
                    'category': 'MISSING_RESOURCE', 'file': rel,
                    'detail': f'CSS url() → отсутствует: {u}',
                    'missing': resolved, 'fixable': True,
                })

    # ===================================================================
    # Фаза 3 — внешние ресурсы (нескачанные домены)
    # ===================================================================

    def _scan_external_assets(self, html_files: list[Path]):
        """Найти ресурсы с нескачанных внешних доменов."""
        missing_domains: dict[str, list[dict]] = {}

        for fpath in html_files:
            self._check()
            try:
                content = fpath.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            rel = str(fpath.relative_to(self.folder))

            for m in _DOTDOT_DOMAIN_RE.finditer(content):
                domain = m.group(2) or m.group(5)
                path = m.group(3) or m.group(6) or ''
                if not domain:
                    continue
                if domain in self._domain_set:
                    continue
                if domain not in missing_domains:
                    missing_domains[domain] = []
                missing_domains[domain].append({
                    'file': rel, 'domain': domain, 'path': path,
                })

        for domain, refs in missing_domains.items():
            unique_paths = set(r['path'] for r in refs)
            files_referencing = set(r['file'] for r in refs)
            self.issues.append({
                'category': 'MISSING_EXTERNAL',
                'file': ', '.join(sorted(files_referencing)[:3]),
                'detail': f'Домен {domain} не скачан — {len(unique_paths)} ресурсов из {len(files_referencing)} файлов',
                'domain': domain,
                'paths': sorted(unique_paths),
                'count': len(unique_paths),
                'fixable': True,
            })

    # ===================================================================
    # Фаза 4 — JS/CSS чанки (_nuxt, _next, chunks)
    # ===================================================================

    def _scan_chunks(self, all_files: list[Path]):
        """Проверить целостность JS/CSS бандлов."""
        chunk_dirs = ('_nuxt', '_next', 'chunks', 'static/js', 'static/css',
                      'build', 'dist', 'assets')

        for fpath in all_files:
            self._check()
            rel = str(fpath.relative_to(self.folder))
            ext = fpath.suffix.lower()

            # Только JS/CSS в папках бандлов
            if ext not in (JS_EXTS | CSS_EXTS):
                continue
            if not any(cd in rel for cd in chunk_dirs):
                continue

            size = fpath.stat().st_size

            # Пустой чанк
            if size == 0:
                self.issues.append({
                    'category': 'BROKEN_CHUNK', 'file': rel,
                    'detail': 'JS/CSS чанк пустой (0 байт)', 'fixable': True,
                })
                continue

            # Слишком маленький JS (< 10 байт — подозрительно)
            if ext in JS_EXTS and size < 10:
                self.issues.append({
                    'category': 'BROKEN_CHUNK', 'file': rel,
                    'detail': f'JS чанк слишком маленький ({size} байт)', 'fixable': True,
                })
                continue

            # Проверка содержимого JS: обрезанный (не закрыт)
            if ext in JS_EXTS and size > 100:
                try:
                    content = fpath.read_bytes()
                    # Последние байты: JS обычно заканчивается на ), }, ;, \n
                    tail = content[-20:].rstrip()
                    if tail and tail[-1:] not in (b')', b'}', b';', b'\n', b'"', b"'", b']'):
                        self.issues.append({
                            'category': 'BROKEN_CHUNK', 'file': rel,
                            'detail': f'JS чанк возможно обрезан (последний символ: {chr(tail[-1])})',
                            'fixable': True,
                        })
                except Exception:
                    pass

    # ===================================================================
    # Фаза 5 — сравнение с оригиналом
    # ===================================================================

    def _compare_with_origin(self, html_files: list[Path]):
        """Сверить ссылки скачанных HTML с оригиналом. Только основной домен."""
        main_dir = self.folder / self._main_domain if self._main_domain else None
        if not main_dir or not main_dir.is_dir():
            return

        main_htmls = [f for f in html_files
                      if self._domain_dir_for(f) == main_dir]
        # Проверяем не более 10 файлов чтобы не грузить оригинал слишком долго
        check_files = main_htmls[:10]

        for fpath in check_files:
            self._check()
            rel_in_domain = str(fpath.relative_to(main_dir))
            url_path = rel_in_domain
            if url_path.endswith('/index.html'):
                url_path = url_path[:-len('index.html')]
            elif url_path.endswith('.html'):
                url_path = url_path[:-5]

            origin_url = f'https://{self._main_domain}/{url_path}'

            try:
                local_content = fpath.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue

            # Извлечь ссылки из локальной копии
            local_hrefs = set()
            for m in re.findall(r'href=["\']([^"\']+)["\']', local_content):
                clean = m.split('?')[0].split('#')[0].strip()
                if clean and not clean.startswith(('data:', 'javascript:', 'mailto:')):
                    local_hrefs.add(clean)

            # Получить оригинал
            try:
                origin_content = self._fetch_url(origin_url)
                if not origin_content:
                    continue
            except Exception:
                continue

            # Извлечь ссылки из оригинала
            origin_hrefs = set()
            for m in re.findall(r'href=["\']([^"\']+)["\']', origin_content):
                clean = m.split('?')[0].split('#')[0].strip()
                if clean and not clean.startswith(('data:', 'javascript:', 'mailto:',
                                                    'http://', 'https://')):
                    origin_hrefs.add(clean)

            # Найти ссылки которые есть в оригинале, но нет в локальной копии
            missing = origin_hrefs - local_hrefs
            # Отфильтровать шум (api, динамические)
            missing = {h for h in missing if not any(
                x in h for x in ('/api/', '__', '.json', 'gtag', 'analytics',
                                  'facebook', 'google', 'twitter')
            )}

            if missing:
                rel = str(fpath.relative_to(self.folder))
                self.issues.append({
                    'category': 'ORIGIN_MISMATCH',
                    'file': rel,
                    'detail': f'{len(missing)} ссылок из оригинала отсутствуют в копии',
                    'missing_links': sorted(missing)[:20],
                    'origin_url': origin_url,
                    'count': len(missing),
                    'fixable': False,
                })

    def _fetch_url(self, url: str) -> str | None:
        """Скачать текст по URL (для сравнения с оригиналом)."""
        try:
            req = UrlRequest(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            })
            resp = urlopen(req, timeout=10)
            if resp.status != 200:
                return None
            return resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return None

    # ===================================================================
    # Исправления
    # ===================================================================

    def start_fix(self, categories: list[str] | None = None):
        if self.status not in ('done', 'stopped'):
            return
        self.status = 'fixing'
        self.phase = 'Исправление'
        self.fixed = []
        self._fix_thread = threading.Thread(
            target=self._run_fix, args=(categories,), daemon=True
        )
        self._fix_thread.start()
        # Ждём завершения (to_thread в app.py уже оборачивает в поток,
        # но если вызвано напрямую — работает синхронно)
        self._fix_thread.join()

    def _run_fix(self, categories: list[str] | None):
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
                    ok = self._fix_redownload(issue)
                elif cat == 'TRUNCATED_HTML':
                    ok = self._fix_redownload(issue)
                elif cat == 'BROKEN_LINK':
                    ok = self._fix_download_missing(issue)
                elif cat == 'MISSING_RESOURCE':
                    ok = self._fix_download_missing(issue)
                elif cat == 'ABSOLUTE_URL':
                    ok = self._fix_absolute_url(issue)
                elif cat == 'WRONG_PATH':
                    ok = self._fix_wrong_path(issue)
                elif cat == 'MISSING_EXTERNAL':
                    ok = self._fix_missing_external(issue)
                elif cat == 'BROKEN_CHUNK':
                    ok = self._fix_redownload(issue)
                elif cat == 'ENCODED_PATH':
                    ok = self._fix_encoded_path(issue)
                elif cat == 'DUPLICATE_LANG':
                    ok = self._fix_duplicate_lang(issue)
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
            try:
                meta = json.loads(meta_path.read_text())
                return meta.get('url', f'https://{self._main_domain}')
            except Exception:
                pass
        return f'https://{self._main_domain}' if self._main_domain else ''

    # -- Исправление: перекачка файла с оригинала -----------------------

    def _fix_redownload(self, issue: dict) -> bool:
        rel = issue['file']
        parts = rel.split('/', 1)
        if len(parts) < 2:
            return False
        domain, path = parts[0], parts[1]
        url = f'https://{domain}/{path}'
        target = self.folder / rel
        return self._download_file(url, target)

    def _fix_download_missing(self, issue: dict) -> bool:
        missing = issue.get('missing', '')
        if not missing:
            return False
        file_rel = issue['file']
        parts = file_rel.split('/', 1)
        if not parts:
            return False
        domain = parts[0]
        url = f'https://{domain}/{missing}'
        target = self.folder / domain / missing
        return self._download_file(url, target)

    # -- Исправление: ../domain/path → /domain/path --------------------

    def _fix_wrong_path(self, issue: dict) -> bool:
        """Переписать ../domain/path ссылки в HTML файлах.
        Скачанный домен → /domain/path
        Нескачанный → https://domain/path (абсолютная ссылка на оригинал)"""
        fpath = self.folder / issue['file']
        if not fpath.exists():
            return False

        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return False

        domain = issue.get('domain', '')
        path = issue.get('path', '')
        if not domain:
            return False

        local_exists = (self.folder / domain).is_dir()

        old_ref = f'../{domain}/{path}'
        if local_exists:
            new_ref = f'/{domain}/{path}'
        else:
            new_ref = f'https://{domain}/{path}'

        new_content = content.replace(old_ref, new_ref)
        if new_content != content:
            fpath.write_text(new_content, encoding='utf-8')
            return True
        return False

    # -- Исправление: нескачанные внешние ресурсы -----------------------

    def _fix_missing_external(self, issue: dict) -> bool:
        """Для нескачанных внешних доменов: переписать ../domain/path → https://domain/path
        во всех HTML файлах, и попробовать докачать ресурсы."""
        domain = issue.get('domain', '')
        paths = issue.get('paths', [])
        if not domain:
            return False

        fixed_count = 0

        # Шаг 1: Переписать ссылки во всех HTML файлах
        main_dir = self.folder / self._main_domain if self._main_domain else None
        if main_dir and main_dir.is_dir():
            for html_file in main_dir.rglob('*.html'):
                try:
                    content = html_file.read_text(encoding='utf-8', errors='ignore')
                    new_content = content
                    for p in paths:
                        new_content = new_content.replace(
                            f'../{domain}/{p}',
                            f'https://{domain}/{p}'
                        )
                    if new_content != content:
                        html_file.write_text(new_content, encoding='utf-8')
                        fixed_count += 1
                except Exception:
                    pass

        # Шаг 2: Попробовать докачать ресурсы (изображения с CDN)
        if any(cdn in domain for cdn in ('cdn.', 'sanity.', 'cloudinary.', 'imgix.')):
            target_dir = self.folder / domain
            for p in paths[:20]:
                target = target_dir / p
                if not target.exists():
                    url = f'https://{domain}/{p}'
                    self._download_file(url, target)
                    fixed_count += 1

        return fixed_count > 0

    # -- Исправление: абсолютные URL → относительные -------------------

    def _fix_absolute_url(self, issue: dict) -> bool:
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

    # -- Исправление: URL-encoded пути (%2F → /) -----------------------

    def _fix_encoded_path(self, issue: dict) -> bool:
        """Декодировать URL-encoded пути в HTML файлах."""
        fpath = self.folder / issue['file']
        if not fpath.exists():
            return False

        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return False

        encoded = issue.get('encoded', '')
        decoded = issue.get('decoded', '')
        if not encoded or not decoded or encoded == decoded:
            return False

        new_content = content.replace(encoded, decoded)
        if new_content == content:
            return False

        try:
            fpath.write_text(new_content, encoding='utf-8')
            return True
        except Exception as e:
            logger.debug(f'Fix encoded path failed {fpath}: {e}')
        return False

    # -- Исправление: дублирование языкового префикса ------------------

    def _fix_duplicate_lang(self, issue: dict) -> bool:
        """Исправить дублирование языкового префикса (/ko/ko/ → /ko/)."""
        fpath = self.folder / issue['file']
        if not fpath.exists():
            return False

        try:
            content = fpath.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return False

        wrong = issue.get('wrong', '')
        correct = issue.get('correct', '')
        if not wrong or not correct or wrong == correct:
            return False

        new_content = content.replace(f'"{wrong}"', f'"{correct}"')
        new_content = new_content.replace(f"'{wrong}'", f"'{correct}'")
        if new_content == content:
            return False

        try:
            fpath.write_text(new_content, encoding='utf-8')
            return True
        except Exception as e:
            logger.debug(f'Fix duplicate lang failed {fpath}: {e}')
        return False

    # -- Утилита скачивания --------------------------------------------

    def _download_file(self, url: str, target: Path) -> bool:
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
            logger.debug(f'Ошибка скачивания {url}: {e}')
            return False


class _Stopped(Exception):
    pass


# =========================================================================
# Публичный API для app.py
# =========================================================================

def start_scan(folder_path: str | Path) -> ScanTask:
    task = ScanTask(folder_path)
    _active_scans[task.scan_id] = task
    task.start()
    return task


def get_scan(scan_id: str) -> ScanTask | None:
    return _active_scans.get(scan_id)


def get_latest_scan(folder_path: str | Path) -> ScanTask | None:
    folder_str = str(Path(folder_path).resolve())
    latest = None
    for task in _active_scans.values():
        if str(task.folder.resolve()) == folder_str:
            if latest is None or task.started_at > latest.started_at:
                latest = task
    return latest


def fix_issues(scan_id: str, categories: list[str] | None = None) -> dict:
    task = _active_scans.get(scan_id)
    if not task:
        return {'error': 'Scan not found'}
    if task.status not in ('done', 'stopped'):
        return {'error': f'Нельзя исправить — статус скана: {task.status}'}
    task.start_fix(categories)
    return task.to_dict()
