"""
HTML Cleaner module - removes trackers and fixes internal links after download.
Called automatically by downloader after job completion.
"""
import re
from pathlib import Path


# Tracking patterns to remove (universal for all sites)
TRACKING_PATTERNS = [
    # === GOOGLE TAG MANAGER ===
    (
        r'<!--\s*Google Tag Manager\s*-->\s*<script>[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?</script>\s*<!--\s*End Google Tag Manager\s*-->',
        'Google Tag Manager'
    ),
    (
        r'<script>\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);</script>',
        'Google Tag Manager'
    ),
    (
        r'<!--\s*Google Tag Manager \(noscript\)\s*-->\s*<noscript>[\s\S]*?googletagmanager\.com/ns\.html[\s\S]*?</noscript>\s*<!--\s*End Google Tag Manager \(noscript\)\s*-->',
        'GTM noscript'
    ),
    (
        r'<noscript>\s*<iframe[^>]*src="[^"]*googletagmanager\.com/ns\.html[^"]*"[^>]*>[\s\S]*?</iframe>\s*</noscript>',
        'GTM noscript'
    ),
    
    # === GOOGLE ANALYTICS ===
    (
        r'<!--\s*Google tag \(gtag\.js\)\s*-->\s*<script[^>]*src="[^"]*googletagmanager\.com/gtag/js[^"]*"[^>]*></script>\s*<script>[\s\S]*?gtag\(\'config\'[^)]*\);\s*</script>',
        'Google Analytics'
    ),
    (
        r'<script[^>]*async[^>]*src="[^"]*googletagmanager\.com/gtag/js[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer[\s\S]*?gtag\(\'config\'[^)]*\);\s*</script>',
        'Google Analytics'
    ),
    
    # === GOOGLE SITE VERIFICATION ===
    (
        r'<meta\s+name="google-site-verification"\s+content="[^"]*"\s*/?>',
        'Google Site Verification'
    ),
    
    # === FACEBOOK PIXEL ===
    (
        r'<!--\s*Facebook Pixel Code\s*-->\s*<script>[\s\S]*?fbevents\.js[\s\S]*?fbq\([^)]*\);\s*</script>\s*<noscript>[\s\S]*?facebook\.com/tr[\s\S]*?</noscript>\s*<!--\s*End Facebook Pixel Code\s*-->',
        'Facebook Pixel'
    ),
    (
        r'<script>\s*!function\(f,b,e,v,n,t,s\)[\s\S]*?fbevents\.js[\s\S]*?fbq\([^)]*\);\s*</script>',
        'Facebook Pixel'
    ),
    (
        r'<noscript>\s*<img[^>]*facebook\.com/tr[^>]*/?>\s*</noscript>',
        'Facebook Pixel noscript'
    ),
    
    # === TRADEDESK ===
    (
        r'<!--\s*Tradedesk\s*-->\s*<script[^>]*src="[^"]*adsrvr\.org[^"]*"[^>]*></script>\s*<script[^>]*>[\s\S]*?TTDUniversalPixelApi[\s\S]*?</script>',
        'TradeDesk'
    ),
    (
        r'<script[^>]*src="[^"]*adsrvr\.org[^"]*"[^>]*></script>',
        'TradeDesk'
    ),
    (
        r'<script[^>]*>[\s\S]*?ttd_dom_ready[\s\S]*?TTDUniversalPixelApi[\s\S]*?</script>',
        'TradeDesk'
    ),
    
    # === BUBBLEUP / MYDATA ===
    (
        r'<script[^>]*src="[^"]*mydatascript\.bubbleup\.com[^"]*"[^>]*></script>',
        'BubbleUp mydata'
    ),
    
    # === SHOPIFY ANALYTICS ===
    (
        r'<script[^>]*id=["\']web-pixels-manager-setup["\'][^>]*>[\s\S]*?</script>',
        'Shopify web-pixels-manager'
    ),
    (
        r'<script[^>]*>[\s\S]*?window\.ShopifyAnalytics[\s\S]*?trekkie[\s\S]*?</script>',
        'Shopify Trekkie'
    ),
    
    # === COOKIEBOT ===
    (
        r'<script[^>]*id="Cookiebot"[^>]*src="[^"]*cookiebot\.com[^"]*"[^>]*>\s*</script>',
        'Cookiebot'
    ),
    
    # === HOTJAR ===
    (
        r'<script>[\s\S]*?hotjar\.com[\s\S]*?</script>',
        'Hotjar'
    ),
    
    # === PRECONNECT TO TRACKING DOMAINS ===
    (
        r'<link[^>]*rel="preconnect"[^>]*href="[^"]*monorail[^"]*"[^>]*/?>',
        'Preconnect monorail'
    ),
    (
        r'<link[^>]*rel="dns-prefetch"[^>]*href="[^"]*shop\.app[^"]*"[^>]*/?>',
        'DNS prefetch shop.app'
    ),
]


def get_downloaded_domains(output_dir: Path) -> list:
    """Find all downloaded domain directories."""
    domains = []
    for item in output_dir.iterdir():
        if item.is_dir() and '.' in item.name:
            # Skip system directories
            if item.name in ['_site', '_wcloner', 'vue-app', 'node_modules']:
                continue
            domains.append(item.name)
    return domains


def convert_paths_for_local_server(content: str, file_path: Path, output_dir: Path, main_domain: str) -> tuple:
    """
    Convert paths in HTML to work with local Vite server.
    Paths are converted to absolute paths from root (e.g., /cdn/... or /pages/...).
    The Vite server will resolve these to the domain folder.
    
    Returns:
        Tuple of (modified_content, links_converted_count)
    """
    links_converted = 0
    
    # Get the domain folder this file is in
    try:
        rel_path = file_path.relative_to(output_dir)
        file_domain = rel_path.parts[0] if rel_path.parts else main_domain
    except ValueError:
        file_domain = main_domain
    
    def replace_path(match):
        nonlocal links_converted
        attr = match.group(1)  # href or src
        path = match.group(2)  # the path
        
        # Skip external URLs, anchors, javascript, data URIs
        if path.startswith(('http://', 'https://', '//', '#', 'javascript:', 'data:', 'mailto:')):
            return match.group(0)
        
        # Handle relative paths (../cdn/... or cdn/...)
        if not path.startswith('/'):
            # Convert relative to absolute from domain root
            # e.g., ../cdn/file.css from pages/home.html -> /cdn/file.css
            import os
            current_dir = file_path.parent.relative_to(output_dir / file_domain) if file_domain else file_path.parent.relative_to(output_dir)
            abs_path = os.path.normpath(os.path.join('/', str(current_dir), path))
            abs_path = abs_path.replace('\\', '/')
            links_converted += 1
            return f'{attr}="{abs_path}"'
        
        # Already absolute path - keep as is
        return match.group(0)
    
    # Match href="..." or src="..."
    pattern = r'(href|src)="([^"]*)"'
    content = re.sub(pattern, replace_path, content)
    
    return content, links_converted


def convert_domain_urls_to_local(content: str, main_domain: str, downloaded_domains: list) -> tuple:
    """
    Convert full URLs (https://domain.com/path) to local paths (/domain.com/path).
    This is the first step - then convert_absolute_to_relative makes them relative.
    
    Returns:
        Tuple of (modified_content, links_converted_count)
    """
    links_converted = 0
    
    # Main domain: https://eagles.com/path → /eagles.com/path
    for domain in [main_domain, f'www.{main_domain}'] + downloaded_domains:
        escaped = re.escape(domain)
        
        # https://domain.com/path → /domain.com/path
        pattern = rf'(href|src)="https?://{escaped}(/[^"]*)"'
        matches = len(re.findall(pattern, content))
        if matches:
            content = re.sub(pattern, rf'\1="/{domain}\2"', content)
            links_converted += matches
        
        # //domain.com/path → /domain.com/path
        pattern = rf'(href|src)="//{escaped}(/[^"]*)"'
        matches = len(re.findall(pattern, content))
        if matches:
            content = re.sub(pattern, rf'\1="/{domain}\2"', content)
            links_converted += matches
    
    return content, links_converted


def process_html_file(file_path: Path, output_dir: Path, main_domain: str, downloaded_domains: list) -> dict:
    """Process a single HTML file: remove trackers and convert to relative paths."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {'error': str(e)}
    
    original = content
    changes = []
    
    # Remove tracking patterns
    for pattern, name in TRACKING_PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        if matches:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
            changes.append(f"Removed {name}")
    
    # Step 1: Convert full URLs to local absolute paths
    content, urls_converted = convert_domain_urls_to_local(content, main_domain, downloaded_domains)
    
    # Step 2: Convert all paths to absolute paths from domain root (for Vite server)
    content, paths_converted = convert_paths_for_local_server(content, file_path, output_dir, main_domain)
    
    total_links = urls_converted + paths_converted
    if total_links > 0:
        changes.append(f"Converted {total_links} links to absolute paths")
    
    # Clean up multiple empty lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    if content != original:
        file_path.write_text(content, encoding='utf-8')
        return {'changes': changes}
    
    return {}


def clean_downloaded_site(output_dir: Path, main_domain: str) -> dict:
    """
    Clean all HTML files in downloaded site:
    - Remove tracking scripts
    - Convert all links to relative paths
    
    Returns statistics about what was cleaned.
    Works directly with project folder (no _site duplication).
    """
    output_dir = Path(output_dir)
    
    if not output_dir.exists():
        return {'error': 'Project directory not found'}
    
    # Find all downloaded domains
    downloaded_domains = get_downloaded_domains(output_dir)
    
    # Find all HTML files in project (excluding system dirs)
    exclude_dirs = {'vue-app', 'node_modules', '_wcloner', '.git'}
    html_files = []
    for html_file in output_dir.rglob('*.html'):
        # Skip files in excluded directories
        if not any(part in exclude_dirs for part in html_file.parts):
            html_files.append(html_file)
    
    stats = {
        'total_files': len(html_files),
        'modified_files': 0,
        'trackers_removed': 0,
        'links_converted': 0,
        'downloaded_domains': downloaded_domains,
    }
    
    for html_file in html_files:
        result = process_html_file(html_file, output_dir, main_domain, downloaded_domains)
        if result.get('changes'):
            stats['modified_files'] += 1
            for change in result['changes']:
                if 'Removed' in change:
                    stats['trackers_removed'] += 1
                if 'Converted' in change:
                    # Extract number from "Converted X links to relative paths"
                    match = re.search(r'Converted (\d+)', change)
                    if match:
                        stats['links_converted'] += int(match.group(1))
    
    return stats
