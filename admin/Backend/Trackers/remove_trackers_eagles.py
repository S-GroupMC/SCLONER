#!/usr/bin/env python3
"""
Remove tracking code and fix internal links for Eagles.com cloned site.

Removes:
1. Google Tag Manager (GTM)
2. Google Analytics (gtag.js)
3. Facebook Pixel
4. TradeDesk tracking
5. Shopify Analytics / Trekkie
6. BubbleUp mydata script
7. Various preconnect links to tracking domains

Fixes:
- Internal links: https://eagles.com/... → /...
- Internal links: //eagles.com/... → /...

Does NOT change:
- External links (ticketmaster.com, eagles.vibee.com, shop.eagles.com, etc.)
- CDN links that are needed for assets

Usage:
    python remove_trackers_eagles.py --dry-run  # Preview changes
    python remove_trackers_eagles.py            # Apply changes
"""

import re
import argparse
from pathlib import Path

# Site directory
SITE_DIR = Path(__file__).parent.parent.parent.parent / "downloads" / "eagles.com" / "_site"
SHOP_DIR = SITE_DIR / "shop.eagles.com"

# Tracking patterns to remove
PATTERNS = [
    # === GOOGLE TAG MANAGER ===
    (
        r'<!--\s*Google Tag Manager\s*-->\s*<script>[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?</script>\s*<!--\s*End Google Tag Manager\s*-->',
        'Google Tag Manager script (with comments)'
    ),
    (
        r'<script>\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);</script>',
        'Google Tag Manager script'
    ),
    (
        r'<!--\s*Google Tag Manager \(noscript\)\s*-->\s*<noscript>[\s\S]*?googletagmanager\.com/ns\.html[\s\S]*?</noscript>\s*<!--\s*End Google Tag Manager \(noscript\)\s*-->',
        'GTM noscript (with comments)'
    ),
    (
        r'<noscript>\s*<iframe[^>]*src="[^"]*googletagmanager\.com/ns\.html[^"]*"[^>]*>[\s\S]*?</iframe>\s*</noscript>',
        'GTM noscript iframe'
    ),
    
    # === GOOGLE ANALYTICS ===
    (
        r'<!--\s*Google tag \(gtag\.js\)\s*-->\s*<script[^>]*src="[^"]*googletagmanager\.com/gtag/js[^"]*"[^>]*></script>\s*<script>[\s\S]*?gtag\(\'config\'[^)]*\);\s*</script>',
        'Google Analytics (gtag.js with comment)'
    ),
    (
        r'<script[^>]*async[^>]*src="[^"]*googletagmanager\.com/gtag/js[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer[\s\S]*?gtag\(\'config\'[^)]*\);\s*</script>',
        'Google Analytics (gtag.js)'
    ),
    
    # === GOOGLE SITE VERIFICATION ===
    (
        r'<meta\s+name="google-site-verification"\s+content="[^"]*"\s*/?>',
        'Google Site Verification'
    ),
    
    # === TRADEDESK ===
    (
        r'<!--\s*Tradedesk\s*-->\s*<script[^>]*src="[^"]*adsrvr\.org[^"]*"[^>]*></script>\s*<script[^>]*>[\s\S]*?TTDUniversalPixelApi[\s\S]*?</script>',
        'TradeDesk tracking'
    ),
    (
        r'<script[^>]*src="[^"]*adsrvr\.org[^"]*"[^>]*></script>',
        'TradeDesk script'
    ),
    (
        r'<script[^>]*>[\s\S]*?ttd_dom_ready[\s\S]*?TTDUniversalPixelApi[\s\S]*?</script>',
        'TradeDesk inline script'
    ),
    
    # === FACEBOOK PIXEL ===
    (
        r'<!--\s*Facebook Pixel Code\s*-->\s*<script>[\s\S]*?fbevents\.js[\s\S]*?fbq\([^)]*\);\s*</script>\s*<noscript>[\s\S]*?facebook\.com/tr[\s\S]*?</noscript>\s*<!--\s*End Facebook Pixel Code\s*-->',
        'Facebook Pixel (with comments)'
    ),
    (
        r'<script>\s*!function\(f,b,e,v,n,t,s\)[\s\S]*?fbevents\.js[\s\S]*?fbq\([^)]*\);\s*</script>',
        'Facebook Pixel script'
    ),
    (
        r'<noscript>\s*<img[^>]*facebook\.com/tr[^>]*/?>\s*</noscript>',
        'Facebook Pixel noscript'
    ),
    
    # === BUBBLEUP MYDATA ===
    (
        r'<script[^>]*src="[^"]*mydatascript\.bubbleup\.com[^"]*"[^>]*></script>',
        'BubbleUp mydata script'
    ),
    
    # === SHOPIFY ANALYTICS ===
    (
        r'<script[^>]*id=["\']web-pixels-manager-setup["\'][^>]*>[\s\S]*?</script>',
        'Shopify web-pixels-manager'
    ),
    (
        r'<script[^>]*>[\s\S]*?window\.ShopifyAnalytics[\s\S]*?trekkie[\s\S]*?</script>',
        'Shopify Trekkie analytics'
    ),
    
    # === PRECONNECT TO TRACKING DOMAINS ===
    (
        r'<link[^>]*rel="preconnect"[^>]*href="[^"]*monorail[^"]*"[^>]*/?>',
        'Preconnect to monorail'
    ),
    (
        r'<link[^>]*rel="dns-prefetch"[^>]*href="[^"]*shop\.app[^"]*"[^>]*/?>',
        'DNS prefetch to shop.app'
    ),
]

# Link rewrite patterns (internal links for all downloaded domains)
LINK_REWRITES = [
    # https://eagles.com/path → /path
    (r'(href|src)="https://eagles\.com(/[^"]*)"', r'\1="\2"'),
    # //eagles.com/path → /path
    (r'(href|src)="//eagles\.com(/[^"]*)"', r'\1="\2"'),
    # https://shop.eagles.com/path → /shop.eagles.com/path
    (r'(href|src)="https://shop\.eagles\.com(/[^"]*)"', r'\1="/shop.eagles.com\2"'),
    # //shop.eagles.com/path → /shop.eagles.com/path
    (r'(href|src)="//shop\.eagles\.com(/[^"]*)"', r'\1="/shop.eagles.com\2"'),
]


def process_file(file_path: Path, dry_run: bool = False) -> dict:
    """Process a single HTML file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {'file': str(file_path), 'error': str(e)}
    
    original = content
    changes = []
    
    # Remove tracking patterns
    for pattern, name in PATTERNS:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE))
        if matches:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
            changes.append(f"Removed {len(matches)}x {name}")
    
    # Rewrite internal links
    for pattern, replacement in LINK_REWRITES:
        matches = list(re.finditer(pattern, content))
        if matches:
            content = re.sub(pattern, replacement, content)
            changes.append(f"Rewrote {len(matches)}x internal links")
    
    # Clean up multiple empty lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    if content != original:
        if not dry_run:
            file_path.write_text(content, encoding='utf-8')
        return {
            'file': str(file_path.relative_to(SITE_DIR)),
            'changes': changes,
            'saved': not dry_run
        }
    
    return None


def show_diagnostics():
    """Show downloaded domains and external links that remain."""
    base_dir = SITE_DIR.parent
    
    print("=" * 60)
    print("ДИАГНОСТИКА: Скачанные домены")
    print("=" * 60)
    
    # Find all domain directories
    downloaded_domains = []
    for item in base_dir.iterdir():
        if item.is_dir() and '.' in item.name and item.name not in ['_site', '_wcloner', 'vue-app', 'node_modules']:
            downloaded_domains.append(item.name)
    
    print(f"\nСкачанные домены ({len(downloaded_domains)}):")
    for domain in sorted(downloaded_domains):
        domain_path = base_dir / domain
        html_count = len(list(domain_path.rglob('*.html')))
        print(f"  ✅ {domain} ({html_count} HTML файлов)")
    
    # Find external links in HTML files
    print(f"\n" + "=" * 60)
    print("ДИАГНОСТИКА: Внешние ссылки (не скачаны)")
    print("=" * 60)
    
    external_links = {}
    for html_file in SITE_DIR.rglob('*.html'):
        try:
            content = html_file.read_text(encoding='utf-8')
            # Find all href links
            for match in re.finditer(r'href="(https?://([^"/]+)[^"]*)"', content):
                url, domain = match.groups()
                # Skip downloaded domains and CDN
                if domain not in downloaded_domains and domain not in ['cdn.shopify.com', 'fonts.googleapis.com', 'fonts.gstatic.com']:
                    if domain not in external_links:
                        external_links[domain] = set()
                    external_links[domain].add(url[:80])
        except:
            pass
    
    if external_links:
        print(f"\nВнешние домены ({len(external_links)}):")
        for domain in sorted(external_links.keys()):
            urls = external_links[domain]
            print(f"  ❌ {domain} ({len(urls)} ссылок)")
            for url in list(urls)[:3]:
                print(f"      {url}")
            if len(urls) > 3:
                print(f"      ... и ещё {len(urls) - 3}")
    else:
        print("\nВсе ссылки ведут на локальные домены.")
    
    print()


def main():
    parser = argparse.ArgumentParser(description='Remove trackers from Eagles.com clone')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without saving')
    parser.add_argument('--file', type=str, help='Process single file')
    parser.add_argument('--diagnose', action='store_true', help='Show downloaded domains and external links')
    args = parser.parse_args()
    
    if not SITE_DIR.exists():
        print(f"ERROR: Site directory not found: {SITE_DIR}")
        return
    
    if args.diagnose:
        show_diagnostics()
        return
    
    print(f"{'[DRY RUN] ' if args.dry_run else ''}Processing Eagles.com site...")
    print(f"Directory: {SITE_DIR}\n")
    
    if args.file:
        files = [SITE_DIR / args.file]
    else:
        files = list(SITE_DIR.rglob('*.html'))
    
    print(f"Found {len(files)} HTML files\n")
    
    results = []
    for f in files:
        result = process_file(f, args.dry_run)
        if result:
            results.append(result)
    
    if results:
        print(f"Modified {len(results)} files:\n")
        for r in results:
            if 'error' in r:
                print(f"  ERROR {r['file']}: {r['error']}")
            else:
                print(f"  {r['file']}")
                for c in r['changes']:
                    print(f"    - {c}")
        print()
    else:
        print("No changes needed.\n")
    
    if args.dry_run:
        print("Run without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
