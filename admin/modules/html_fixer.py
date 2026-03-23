"""
HTML Fixer module - fixes HTML corruption caused by wget2 --convert-links (-k).

wget2 -k does text-based URL replacement and on minified HTML it inserts
the page URL inside unrelated words/attributes, e.g.:
    rel="stylesheet" -> rel="styleshttps://domain.com/pages/heet"
    defer            -> deferhttps://domain.com/blogs/

This module detects the corrupted URLs and removes them, restoring the
original text. Works universally with any domain.

Usage:
    from admin.modules.html_fixer import fix_wget_corrupted_html
    stats = fix_wget_corrupted_html('/path/to/downloads/sitename')
"""
import re
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def detect_domains(output_dir: Path) -> list:
    """Auto-detect downloaded domain folders in the output directory."""
    domains = []
    for item in output_dir.iterdir():
        if item.is_dir() and '.' in item.name:
            if item.name in ('vue-app', 'node_modules', '_wcloner', '.git', '_site'):
                continue
            domains.append(item.name)
    return domains


def get_page_urls_for_file(file_path: Path, domain_dir: Path, domain: str) -> list:
    """
    Determine which URLs wget2 could have inserted into this file.
    
    For file: eagles.com/pages/home.html
    wget2 inserts: https://eagles.com/pages/ (the directory URL)
    
    For file: eagles.com/blogs/news.html
    wget2 inserts: https://eagles.com/blogs/ (the directory URL)
    
    Returns list of possible corrupted URL strings.
    """
    try:
        rel = file_path.relative_to(domain_dir)
    except ValueError:
        return []
    
    urls = []
    # Build directory-based URL (most common corruption)
    parts = list(rel.parts)
    if len(parts) > 1:
        # e.g. pages/home.html -> https://domain/pages/
        dir_path = '/'.join(parts[:-1])
        urls.append(f'https://{domain}/{dir_path}/')
        urls.append(f'http://{domain}/{dir_path}/')
        # Also without trailing slash
        urls.append(f'https://{domain}/{dir_path}')
        urls.append(f'http://{domain}/{dir_path}')
    
    # Root-level file: e.g. index.html -> https://domain/
    urls.append(f'https://{domain}/')
    urls.append(f'http://{domain}/')
    
    return urls


def find_corrupted_insertions(content: str, page_url: str) -> list:
    """
    Find all places where page_url is inserted inside words/attributes.
    
    Corruption pattern: [a-zA-Z0-9_-]URL[a-zA-Z0-9_-]
    The URL appears between parts of what was originally a single word.
    
    Also catches: standalone URL inserted as bare text between tags
    e.g.: >https://eagles.com/pages/<link ...
    
    Returns list of (full_match, replacement) tuples.
    """
    corruptions = []
    escaped_url = re.escape(page_url)
    
    # Pattern 1: URL inserted inside a word (most common)
    # [letter(s)] URL [letter(s)]  -> letters were one word
    pattern1 = re.compile(
        r'([a-zA-Z0-9_-])(' + escaped_url + r')([a-zA-Z0-9_-])'
    )
    for m in pattern1.finditer(content):
        original_word_parts = m.group(1) + m.group(3)
        corruptions.append((m.group(0), original_word_parts, m.start()))
    
    # Pattern 2: URL at start of text (before a letter), preceded by non-letter
    # e.g.: >https://eagles.com/pages/heet"  or  "https://eagles.com/pages/defer"
    # where it was ">sheet" or "defer"
    pattern2 = re.compile(
        r'([^a-zA-Z0-9_-])(' + escaped_url + r')([a-zA-Z0-9_-])'
    )
    for m in pattern2.finditer(content):
        # Only if the char before is not part of a word and URL touches a letter after
        # This catches: >URL<letter> -> ><letter>
        corruptions.append((m.group(0), m.group(1) + m.group(3), m.start()))
    
    # Pattern 3: URL after a letter, before non-letter
    # e.g.: styleshttps://eagles.com/pages/> -> styles>
    pattern3 = re.compile(
        r'([a-zA-Z0-9_-])(' + escaped_url + r')([^a-zA-Z0-9_-])'
    )
    for m in pattern3.finditer(content):
        corruptions.append((m.group(0), m.group(1) + m.group(3), m.start()))
    
    # Deduplicate by position
    seen_positions = set()
    unique = []
    for full, replacement, pos in corruptions:
        if pos not in seen_positions:
            seen_positions.add(pos)
            unique.append((full, replacement))
    
    return unique


def fix_single_file(file_path: Path, domain_dir: Path, domain: str, dry_run: bool = False) -> dict:
    """
    Fix wget2 -k corruptions in a single HTML file.
    
    Returns dict with stats about what was fixed.
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return {'error': str(e)}
    
    original = content
    total_fixes = 0
    fix_details = []
    
    # Get possible corrupted URLs for this file
    page_urls = get_page_urls_for_file(file_path, domain_dir, domain)
    
    for page_url in page_urls:
        corruptions = find_corrupted_insertions(content, page_url)
        for full_match, replacement in corruptions:
            if full_match in content:
                content = content.replace(full_match, replacement, 1)
                total_fixes += 1
                if len(fix_details) < 20:
                    fix_details.append(f'{full_match[:60]} -> {replacement[:40]}')
    
    # Also check cross-file corruption: other pages' URLs might be in this file
    # e.g. home.html might have corruption from pages/ directory URL
    # We already handle this via get_page_urls_for_file returning multiple URLs
    
    if content != original and not dry_run:
        file_path.write_text(content, encoding='utf-8')
    
    return {
        'fixes': total_fixes,
        'details': fix_details,
        'modified': content != original
    }


def clean_bare_path_fragments(content: str, domain_dir: Path, domain: str) -> tuple:
    """
    Remove bare path fragments left after URL removal.
    
    After removing https://eagles.com/pages/, leftover "pages/" can remain
    as bare text before tags, attributes, or in CSS. This function removes them.
    
    Returns (cleaned_content, fix_count)
    """
    fixes = 0
    
    # Collect all subdirectory names in the domain folder
    dir_names = set()
    for d in domain_dir.iterdir():
        if d.is_dir() and d.name not in ('vue-app', 'node_modules', '_wcloner', '.git', '_site'):
            dir_names.add(d.name)
    
    if not dir_names:
        return content, 0
    
    for dir_name in dir_names:
        fragment = dir_name + '/'
        
        # Pattern 1: "pages/ <tag" or "pages/<tag" - bare fragment before HTML tag
        pattern1 = re.compile(r'(?<![a-zA-Z0-9_/"=-])' + re.escape(fragment) + r'\s*(<)')
        count1 = len(pattern1.findall(content))
        if count1:
            content = pattern1.sub(r'\1', content)
            fixes += count1
        
        # Pattern 2: "pages/      url(" - bare fragment before CSS url()
        pattern2 = re.compile(r'(?<![a-zA-Z0-9_/"=-])' + re.escape(fragment) + r'\s+(url\()')
        count2 = len(pattern2.findall(content))
        if count2:
            content = pattern2.sub(r'\1', content)
            fixes += count2
        
        # Pattern 3: "pages/      href=" or "pages/      src=" - bare fragment before attribute
        pattern3 = re.compile(r'(?<![a-zA-Z0-9_/"=-])' + re.escape(fragment) + r'\s+(href=|src=|srcset=)')
        count3 = len(pattern3.findall(content))
        if count3:
            content = pattern3.sub(r'\1', content)
            fixes += count3
        
        # Pattern 4: "pages/ >" - bare fragment before closing >
        pattern4 = re.compile(r'(?<![a-zA-Z0-9_/"=-])' + re.escape(fragment) + r'\s*(>)')
        count4 = len(pattern4.findall(content))
        if count4:
            content = pattern4.sub(r'\1', content)
            fixes += count4
    
    return content, fixes


def _collect_all_dir_urls(output_dir: Path, domains: list, exclude_dirs: set) -> list:
    """Collect all possible corrupted directory URLs (once, for all files)."""
    all_urls = []
    for domain in domains:
        domain_dir = output_dir / domain
        if not domain_dir.is_dir():
            continue
        for d in domain_dir.rglob('*'):
            if not d.is_dir():
                continue
            if any(part in exclude_dirs for part in d.parts):
                continue
            try:
                rel = d.relative_to(domain_dir)
                dir_path = str(rel).replace('\\', '/')
                all_urls.append(f'https://{domain}/{dir_path}/')
            except ValueError:
                pass
        # Root URL
        all_urls.append(f'https://{domain}/')
    # Deduplicate, sort longest first (longer URLs should be replaced first)
    all_urls = sorted(set(all_urls), key=len, reverse=True)
    return all_urls


def fix_wget_corrupted_html(output_dir, dry_run: bool = False) -> dict:
    """
    Fix all HTML files in a downloaded site directory.
    
    Args:
        output_dir: Path to the site download directory (e.g. downloads/eagles.com/)
        dry_run: If True, only report but don't modify files
    
    Returns:
        Dict with statistics about fixes applied.
    """
    output_dir = Path(output_dir)
    
    if not output_dir.exists():
        return {'error': 'Directory not found', 'output_dir': str(output_dir)}
    
    domains = detect_domains(output_dir)
    if not domains:
        return {'error': 'No domain directories found', 'output_dir': str(output_dir)}
    
    logger.info(f'[html_fixer] Detected domains: {domains}')
    
    exclude_dirs = {'vue-app', 'node_modules', '_wcloner', '.git', '_site'}
    
    # Pre-collect ALL possible corrupted URLs once
    all_dir_urls = _collect_all_dir_urls(output_dir, domains, exclude_dirs)
    logger.info(f'[html_fixer] Collected {len(all_dir_urls)} directory URLs to check')
    
    stats = {
        'domains': domains,
        'total_files': 0,
        'modified_files': 0,
        'total_fixes': 0,
        'dry_run': dry_run,
        'files': [],
    }
    
    # Single pass: for each HTML file, try ALL directory URLs
    for domain in domains:
        domain_dir = output_dir / domain
        if not domain_dir.is_dir():
            continue
        
        html_files = [
            f for f in domain_dir.rglob('*.html')
            if not any(part in exclude_dirs for part in f.parts)
        ]
        
        logger.info(f'[html_fixer] Domain {domain}: {len(html_files)} HTML files')
        
        for html_file in html_files:
            stats['total_files'] += 1
            
            try:
                content = html_file.read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                logger.warning(f'[html_fixer] Error reading {html_file}: {e}')
                continue
            
            original = content
            file_fixes = 0
            fix_details = []
            
            # Step 1: Remove corrupted URL insertions inside words
            has_any = False
            for domain_name in domains:
                if f'https://{domain_name}/' in content:
                    has_any = True
                    break
            
            if has_any:
                for dir_url in all_dir_urls:
                    if dir_url not in content:
                        continue
                    corruptions = find_corrupted_insertions(content, dir_url)
                    for full_match, replacement in corruptions:
                        if full_match in content:
                            content = content.replace(full_match, replacement, 1)
                            file_fixes += 1
                            if len(fix_details) < 10:
                                fix_details.append(
                                    f'{full_match[:60]} -> {replacement[:40]}'
                                )
            
            # Step 2: Remove bare path fragments (pages/, blogs/, etc.)
            content, frag_fixes = clean_bare_path_fragments(
                content, domain_dir, domain
            )
            file_fixes += frag_fixes
            
            if content != original:
                if not dry_run:
                    html_file.write_text(content, encoding='utf-8')
                stats['modified_files'] += 1
                stats['total_fixes'] += file_fixes
                rel_path = str(html_file.relative_to(output_dir))
                stats['files'].append({
                    'path': rel_path,
                    'fixes': file_fixes,
                    'details': fix_details[:5]
                })
                logger.info(f'[html_fixer] Fixed {rel_path}: {file_fixes} corruptions')
    
    logger.info(f'[html_fixer] Done: {stats["total_fixes"]} fixes in {stats["modified_files"]} files')
    return stats
