#!/usr/bin/env python3
"""
Remove tracking code from Rosalia template HTML files.
SAFE VERSION - only removes external trackers, keeps layout-critical code intact.

Removes:
1. Google Tag Manager (GTM) script + noscript (index.html)
2. Shopify Analytics / Trekkie (27 eu/ files)
3. Shopify web-pixels-manager (27 eu/ files)
4. Shopify monorail/abandonment tracking (27 eu/ files)
5. Facebook Pixel / connect.facebook.net (27 eu/ files)
6. Shopify __st tracking config
7. Shopify PaypalV4VisibilityTracking
8. Shopify privacy-banner / storefront-banner
9. EasyLocation extension
10. Shopify shopify-features JSON
11. Preconnect links to tracking domains

Does NOT remove (would break layout):
- Shopify theme JS (component.js, utilities.js, etc.)
- Shopify CDN asset links
- Shopify shop config (Shopify.shop, Shopify.locale)
- jQuery

Usage:
    python remove_trackers_rosalia.py --dry-run  # Preview changes
    python remove_trackers_rosalia.py             # Apply changes
"""

import re
import argparse
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
ROSALIA_DIR = TEMPLATES_DIR / "rosalia"

# SAFE patterns - only external tracking scripts
PATTERNS = [
    # === GOOGLE TAG MANAGER ===

    # 1. GTM script (multiline)
    (
        r'<script>\s*\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);\s*</script>',
        'Google Tag Manager script'
    ),

    # 2. GTM noscript iframe (with comment)
    (
        r'<!--\s*Google Tag Manager[^-]*-->\s*<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>\s*</iframe>\s*</noscript>\s*(?:<!--\s*End Google Tag Manager\s*-->)?',
        'GTM noscript iframe (with comment)'
    ),

    # 3. GTM noscript iframe (no comment, also // protocol)
    (
        r'<noscript>\s*<iframe[^>]*src="(?:https:)?//www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>\s*</iframe>\s*</noscript>',
        'GTM noscript iframe'
    ),

    # 4. GTM comment blocks
    (
        r'<!--\s*Google Tag Manager[^-]*-->\s*\n*\s*<!--\s*End Google Tag Manager[^-]*-->',
        'GTM empty comments'
    ),

    # === FACEBOOK PIXEL ===

    # 5. Facebook Pixel full block with comments
    (
        r'<!--\s*Facebook Pixel Code\s*-->\s*<script>[\s\S]*?fbq\([\'"]init[\'"][\s\S]*?</script>\s*<noscript>[\s\S]*?facebook\.com/tr[\s\S]*?</noscript>\s*<!--\s*End Facebook Pixel Code\s*-->',
        'Facebook Pixel (full block)'
    ),

    # 6. Facebook Pixel (fbq init)
    (
        r"<script>[\s\S]*?fbq\s*\(\s*['\"]init['\"][\s\S]*?</script>",
        'Facebook Pixel (fbq init)'
    ),

    # 7. Facebook connect.facebook.net script
    (
        r'<script[^>]*src="https://connect\.facebook\.net/[^"]*"[^>]*>\s*</script>',
        'Facebook SDK script'
    ),

    # 8. Facebook noscript pixel image
    (
        r'<noscript>\s*<img[^>]*src="https://www\.facebook\.com/tr[^"]*"[^>]*/?>\s*</noscript>',
        'Facebook noscript pixel'
    ),

    # === SHOPIFY ANALYTICS / TREKKIE ===

    # 9. Shopify Analytics/Trekkie full block
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};[\s\S]*?</script>\s*<script class="analytics">[\s\S]*?trekkie\.load\([\s\S]*?\);\s*</script>',
        'Shopify Analytics/Trekkie'
    ),

    # 10. Shopify Analytics meta block
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};\s*window\.ShopifyAnalytics\.meta\s*=[\s\S]*?</script>',
        'Shopify Analytics meta'
    ),

    # 11. Shopify analytics class script (trekkie)
    (
        r'<script class="analytics">[\s\S]*?trekkie[\s\S]*?</script>',
        'Shopify Trekkie script'
    ),

    # === SHOPIFY WEB-PIXELS-MANAGER ===

    # 12. Shopify web-pixels-manager
    (
        r'<script id="web-pixels-manager-setup">[\s\S]*?</script>',
        'Shopify web-pixels-manager'
    ),

    # 13. Shopify analytics JSON
    (
        r'<script id="shop-js-analytics" type="application/json">[^<]*</script>',
        'Shopify analytics JSON'
    ),

    # === SHOPIFY MONORAIL / ABANDONMENT ===

    # 14. Shopify monorail/abandonment tracking
    (
        r'<link href="https://monorail-edge\.shopifysvc\.com" rel="dns-prefetch">\s*<script>\(function\(\)\{if \("sendBeacon"[\s\S]*?handle_abandonment_event[\s\S]*?\}\(\)\);</script>',
        'Shopify Abandonment Tracking'
    ),

    # 15. Monorail dns-prefetch (standalone)
    (
        r'<link\s+href="https://monorail-edge\.shopifysvc\.com"\s+rel="dns-prefetch"\s*/?>',
        'Monorail dns-prefetch'
    ),

    # === SHOPIFY __st TRACKING ===

    # 16. Shopify __st tracking config
    (
        r'<script id="__st">[\s\S]*?</script>',
        'Shopify __st tracking'
    ),

    # === SHOPIFY PAYPAL VISIBILITY TRACKING ===

    # 17. ShopifyPaypalV4VisibilityTracking
    (
        r'<script>\s*window\.ShopifyPaypalV4VisibilityTracking\s*=\s*true;\s*</script>',
        'Shopify PayPal Visibility Tracking'
    ),

    # === SHOPIFY PRIVACY BANNER ===

    # 18. Shopify privacy-banner / storefront-banner
    (
        r'<script[^>]*src="[^"]*privacy-banner/storefront-banner[^"]*"[^>]*>\s*</script>',
        'Shopify privacy banner'
    ),

    # === EASYLOCATION EXTENSION ===

    # 19. EasyLocation Shopify extension
    (
        r'<script[^>]*src="https://cdn\.shopify\.com/extensions/[^"]*easylocation[^"]*"[^>]*>\s*</script>',
        'EasyLocation extension'
    ),

    # === SHOPIFY FEATURES JSON ===

    # 20. Shopify features JSON (contains accessToken, analytics config)
    (
        r'<script id="shopify-features" type="application/json">[^<]*</script>',
        'Shopify features JSON'
    ),

    # === TREKKIE STOREFRONT SCRIPT TAGS ===

    # 21. Trekkie storefront script (cdn/s/trekkie.storefront.*)
    (
        r'<script[^>]*src="[^"]*trekkie\.storefront[^"]*"[^>]*>\s*</script>',
        'Trekkie storefront script'
    ),

    # === SHOPIFY WPM (Web Pixel Manager) SCRIPT ===

    # 22. Shopify wpm script
    (
        r'<script[^>]*src="[^"]*cdn/wpm/[^"]*"[^>]*>\s*</script>',
        'Shopify WPM script'
    ),

    # === SHOPIFY SHOP_EVENTS_LISTENER ===

    # 23. Shopify shop_events_listener
    (
        r'<script[^>]*src="[^"]*shop_events_listener[^"]*"[^>]*>\s*</script>',
        'Shopify shop_events_listener'
    ),

    # === PRECONNECT TO TRACKING DOMAINS ===

    # 24. Preconnect to tracking domains
    (
        r'<link\s+rel="preconnect"\s+href="https://(?:connect\.facebook\.net|www\.googletagmanager\.com|www\.google-analytics\.com)"[^>]*/?>',
        'Preconnect to tracker'
    ),

    # 25. DNS-prefetch to tracking domains
    (
        r'<link\s+rel="dns-prefetch"\s+href="https://(?:connect\.facebook\.net|www\.googletagmanager\.com|www\.google-analytics\.com)"[^>]*/?>',
        'DNS-prefetch to tracker'
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
    parser = argparse.ArgumentParser(description='Remove tracking code from Rosalia template (SAFE)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--dir', type=str, help='Custom directory to process')
    args = parser.parse_args()

    directory = Path(args.dir) if args.dir else ROSALIA_DIR

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1

    print(f"Removing trackers from: {directory}")
    print("SAFE MODE: GTM, Facebook, Shopify Analytics/Trekkie/WPM/Monorail, EasyLocation")
    process_directory(directory, dry_run=args.dry_run)

    return 0


if __name__ == '__main__':
    exit(main())
