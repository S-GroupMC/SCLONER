#!/usr/bin/env python3
"""
Remove tracking code from Tomorrowland template HTML files.
SAFE VERSION - only removes external trackers, keeps layout-critical code intact.

Removes:
1. Google Tag Manager (GTM) script + noscript (16 GTM IDs, 192 files)
2. Google Analytics 4 (GA4) gtag.js (7 GA4 + 1 UA)
3. Cookiebot consent manager (causes __tcfapi errors, 129 files)
4. Facebook Pixel (connect.facebook.net + fbq, 63 files)
5. Shopify Analytics / Trekkie (30 files)
6. Shopify web-pixels-manager (30 files)
7. Shopify monorail/abandonment tracking (32 files)
8. KiwiSizing Shopify app (30 files)
9. Reviews.io widgets (30 files)
10. Google Site Verification meta tags (30 files)
11. Preconnect links to tracking domains

Does NOT remove (would break layout):
- Webflow JS (webflow.js) - breaks foundation/library pages
- Shopify currencies.js - needed for store UI
- Shopify CDN links - needed for assets
- Bugsnag/Plausible/Adglare - in JS bundles, not in HTML

Usage:
    python remove_trackers_tomorrowland.py --dry-run  # Preview changes
    python remove_trackers_tomorrowland.py            # Apply changes
"""

import re
import argparse
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "frontend" / "src" / "templates"
TOMORROWLAND_DIR = TEMPLATES_DIR / "tomorrow"

# SAFE patterns - only external tracking scripts
PATTERNS = [
    # === GOOGLE TAG MANAGER (16 different GTM IDs) ===
    
    # 1. GTM script (multiline with spaces)
    (
        r'<script>\s*\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);\s*</script>',
        'Google Tag Manager script'
    ),
    
    # 2. GTM script (compact, no spaces)
    (
        r'<script>\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];w\[l\]\.push\(\{\'gtm\.start\':\s*new Date\(\)\.getTime\(\),event:\'gtm\.js\'\}\);var f=d\.getElementsByTagName\(s\)\[0\],\s*j=d\.createElement\(s\),dl=l!=\'dataLayer\'\?\'&l=\'\+l:\'\';j\.async=true;j\.src=\s*\'https://www\.googletagmanager\.com/gtm\.js\?id=\'\+i\+dl;f\.parentNode\.insertBefore\(j,f\);\s*\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);</script>',
        'Google Tag Manager script (compact)'
    ),
    
    # 3. GTM noscript iframe (https)
    (
        r'<!--\s*Google Tag Manager \(noscript\).*?-->\s*<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*></iframe>\s*</noscript>\s*(?:<!--\s*End Google Tag Manager \(noscript\)\s*-->)?',
        'GTM noscript iframe (with comment)'
    ),
    
    # 4. GTM noscript iframe (no comment)
    (
        r'<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>\s*</iframe>\s*</noscript>',
        'GTM noscript iframe'
    ),
    
    # === GOOGLE ANALYTICS 4 (7 GA4 IDs + 1 UA) ===
    
    # 5. GA4 with comment
    (
        r'<!--\s*Google tag \(gtag\.js\).*?-->\s*<script[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];\s*function\s+gtag\(\)\{dataLayer\.push\(arguments\);\}\s*gtag\(\'js\',\s*new\s+Date\(\)\);\s*gtag\(\'config\',\s*\'[^\']+\'\);\s*</script>',
        'Google Analytics 4 (with comment)'
    ),
    
    # 6. GA4 without comment
    (
        r'<script[^>]*async[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];\s*function\s+gtag\(\)\{dataLayer\.push\(arguments\);\}\s*gtag\(\'js\',\s*new\s+Date\(\)\);\s*gtag\(\'config\',\s*\'[^\']+\'\);\s*</script>',
        'Google Analytics 4'
    ),
    
    # 7. Standalone gtag.js script tag (without config block)
    (
        r'<script[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*>\s*</script>',
        'gtag.js script tag'
    ),
    
    # === COOKIEBOT (3 different cbid, 129 files) ===
    
    # 8. Cookiebot script tag
    (
        r'<script[^>]*id="Cookiebot"[^>]*src="https://consent\.cookiebot\.com/uc\.js"[^>]*>\s*</script>',
        'Cookiebot script'
    ),
    
    # 9. Cookiebot declaration script
    (
        r'<script[^>]*id="CookieDeclaration"[^>]*src="https://consent\.cookiebot\.com/[^"]*"[^>]*>\s*</script>',
        'Cookiebot declaration'
    ),
    
    # 10. Cookiebot inline config
    (
        r'<script[^>]*>\s*window\.addEventListener\([\s\S]*?CookieConsent[\s\S]*?\);\s*</script>',
        'Cookiebot inline config'
    ),
    
    # === FACEBOOK PIXEL (63 files) ===
    
    # 11. Facebook Pixel full block with comments
    (
        r'<!--\s*Facebook Pixel Code\s*-->\s*<script>[\s\S]*?fbq\([\'"]init[\'"][\s\S]*?</script>\s*<noscript>[\s\S]*?facebook\.com/tr[\s\S]*?</noscript>\s*<!--\s*End Facebook Pixel Code\s*-->',
        'Facebook Pixel (full block)'
    ),
    
    # 12. Facebook Pixel (fbq init without comments)
    (
        r"<script>[\s\S]*?fbq\s*\(\s*['\"]init['\"][\s\S]*?</script>",
        'Facebook Pixel (fbq init)'
    ),
    
    # 13. Facebook connect.facebook.net script
    (
        r'<script[^>]*src="https://connect\.facebook\.net/[^"]*"[^>]*>\s*</script>',
        'Facebook SDK script'
    ),
    
    # 14. Facebook noscript pixel image
    (
        r'<noscript>\s*<img[^>]*src="https://www\.facebook\.com/tr[^"]*"[^>]*/?>\s*</noscript>',
        'Facebook noscript pixel'
    ),
    
    # === SHOPIFY ANALYTICS (30 files - blogs/store) ===
    
    # 15. Shopify Analytics/Trekkie full block
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};[\s\S]*?</script>\s*<script class="analytics">[\s\S]*?trekkie\.load\([\s\S]*?\);\s*</script>',
        'Shopify Analytics/Trekkie'
    ),
    
    # 16. Shopify Analytics meta block
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};\s*window\.ShopifyAnalytics\.meta\s*=[\s\S]*?</script>',
        'Shopify Analytics meta'
    ),
    
    # 17. Shopify analytics class script (trekkie)
    (
        r'<script class="analytics">[\s\S]*?trekkie[\s\S]*?</script>',
        'Shopify Trekkie script'
    ),
    
    # 18. Shopify web-pixels-manager
    (
        r'<script id="web-pixels-manager-setup">[\s\S]*?</script>',
        'Shopify web-pixels-manager'
    ),
    
    # 19. Shopify analytics JSON
    (
        r'<script id="shop-js-analytics" type="application/json">[^<]*</script>',
        'Shopify analytics JSON'
    ),
    
    # 20. Shopify monorail/abandonment tracking
    (
        r'<link href="https://monorail-edge\.shopifysvc\.com" rel="dns-prefetch">\s*<script>\(function\(\)\{if \("sendBeacon"[\s\S]*?handle_abandonment_event[\s\S]*?\}\(\)\);</script>',
        'Shopify Abandonment Tracking'
    ),
    
    # === KIWISIZING (30 files) ===
    
    # 21. KiwiSizing inline config
    (
        r'<script>\s*window\.KiwiSizing\s*=\s*window\.KiwiSizing\s*===\s*undefined\s*\?\s*\{\}\s*:\s*window\.KiwiSizing;\s*KiwiSizing\.shop\s*=\s*"[^"]*";\s*</script>',
        'KiwiSizing config'
    ),
    
    # 22. KiwiSizing external script
    (
        r'<script[^>]*src="[^"]*kiwisizing[^"]*"[^>]*>\s*</script>',
        'KiwiSizing script'
    ),
    
    # === REVIEWS.IO (30 files) ===
    
    # 23. Reviews.io scripts
    (
        r'<script[^>]*src="[^"]*reviews\.io[^"]*"[^>]*>[\s\S]*?</script>',
        'Reviews.io script'
    ),
    
    # === GOOGLE SITE VERIFICATION (30 files) ===
    
    # 24. Google site verification meta
    (
        r'<meta\s+name="google-site-verification"\s+content="[^"]*"\s*/?>',
        'Google Site Verification'
    ),
    
    # === PRECONNECT TO TRACKING DOMAINS ===
    
    # 25. Preconnect to tracking domains
    (
        r'<link\s+rel="preconnect"\s+href="https://(?:consent\.cookiebot\.com|connect\.facebook\.net|www\.googletagmanager\.com)"[^>]*/?>',
        'Preconnect to tracker'
    ),
    
    # 26. DNS-prefetch to tracking domains
    (
        r'<link\s+rel="dns-prefetch"\s+href="https://(?:consent\.cookiebot\.com|connect\.facebook\.net|www\.googletagmanager\.com)"[^>]*/?>',
        'DNS-prefetch to tracker'
    ),
    
    # === EMPTY GTM COMMENTS (cleanup) ===
    
    # 27. Empty GTM comments
    (
        r'<!--\s*Google Tag Manager\s*-->\s*\n*\s*<!--\s*End Google Tag Manager\s*-->',
        'Empty GTM comments'
    ),
    
    # 28. Empty GTM noscript comments
    (
        r'<!--\s*Google Tag Manager \(noscript\)\s*-->\s*\n*\s*<!--\s*End Google Tag Manager \(noscript\)\s*-->',
        'Empty GTM noscript comments'
    ),
]

stats = {
    'files_scanned': 0,
    'files_modified': 0,
    'patterns_removed': {}
}


def remove_trackers_from_file(filepath: Path, dry_run: bool = True) -> bool:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return False
    
    modified = False
    
    for pattern, name in PATTERNS:
        try:
            regex = re.compile(pattern, re.DOTALL | re.IGNORECASE)
            matches = regex.findall(content)
            if matches:
                content = regex.sub('', content)
                modified = True
                
                if name not in stats['patterns_removed']:
                    stats['patterns_removed'][name] = 0
                stats['patterns_removed'][name] += len(matches)
                
                if dry_run:
                    print(f"  Would remove: {name} ({len(matches)} match(es))")
        except Exception as e:
            print(f"  Error with pattern '{name}': {e}")
    
    if modified and not dry_run:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"  Error writing {filepath}: {e}")
            return False
    
    return modified


def process_directory(directory: Path, dry_run: bool = True):
    html_files = list(directory.rglob('*.html'))
    total = len(html_files)
    
    print(f"\nFound {total} HTML files in {directory}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLYING CHANGES'}\n")
    
    for i, filepath in enumerate(html_files, 1):
        stats['files_scanned'] += 1
        relative_path = filepath.relative_to(directory)
        
        modified = remove_trackers_from_file(filepath, dry_run)
        
        if modified:
            stats['files_modified'] += 1
            if stats['files_modified'] <= 20 or not dry_run:
                print(f"[{i}/{total}] {relative_path}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files scanned: {stats['files_scanned']}")
    print(f"Files {'would be ' if dry_run else ''}modified: {stats['files_modified']}")
    print("\nPatterns removed:")
    for name, count in sorted(stats['patterns_removed'].items(), key=lambda x: -x[1]):
        print(f"  - {name}: {count}")
    
    if dry_run:
        print("\n[DRY RUN] No files were modified. Run without --dry-run to apply changes.")


def main():
    parser = argparse.ArgumentParser(description='Remove tracking code from Tomorrowland template (SAFE)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--dir', type=str, help='Custom directory to process')
    args = parser.parse_args()
    
    directory = Path(args.dir) if args.dir else TOMORROWLAND_DIR
    
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1
    
    print(f"Removing trackers from: {directory}")
    print("SAFE MODE: GTM, GA4, Cookiebot, Facebook, Shopify, KiwiSizing, Reviews.io")
    process_directory(directory, dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    exit(main())
