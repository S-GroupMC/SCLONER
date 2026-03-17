#!/usr/bin/env python3
"""
Remove tracking code from The Weeknd template HTML files.
Processes both www.theweeknd.com (tour) and xo.store (store) directories.

Removes:
=== TOUR (www.theweeknd.com) ===
1. Google Tag Manager (GTM) - gtm4wp script + noscript iframe
2. dataLayer initialization scripts
3. wp-emoji scripts (_wpemojiSettings)
4. Appreciation Engine / downloadJSAtOnload
5. UMGECRM scripts (umg-ecrm-frontend.js + inline config)
6. Incapsula bot protection scripts
7. GTM form-move-tracker script

=== STORE (xo.store) ===
8. Google Tag Manager (GTM) - script + noscript iframe
9. dataLayer push scripts
10. Shopify Analytics / Trekkie (full block)
11. Shopify web-pixels-manager
12. Shopify monorail/abandonment tracking
13. Shopify perf-kit
14. Shopify async loader (trackedlink, privy, rise-ai, incartupsell, size-guides)
15. Hotjar
16. Transcend/airgap consent manager
17. Vice/sdiapi (UMG tracking)
18. Google site verification meta
19. Privy widget CSS

=== BOTH ===
20. Preconnect/dns-prefetch to tracking domains

Does NOT remove (would break layout):
- Shopify.shop / Shopify.locale / Shopify.currency config
- Shopify CDN links for assets
- Theme bundle JS (alpine, theme, product, cart-drawer, etc.)
- Store fonts CSS

Usage:
    python remove_trackers_theweeknd.py --dry-run  # Preview changes
    python remove_trackers_theweeknd.py             # Apply changes
"""

import re
import argparse
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "frontend" / "src" / "templates"
THEWEEKND_DIR = TEMPLATES_DIR / "theweeknd"

# Patterns to remove (compiled regex)
PATTERNS = [
    # =============================================
    # GOOGLE TAG MANAGER
    # =============================================

    # 1. GTM script (gtm4wp WordPress plugin)
    (
        r'<!--\s*Google Tag Manager for WordPress by gtm4wp\.com\s*-->\s*'
        r'<script[^>]*>\s*var\s+gtm4wp_datalayer_name\s*=\s*"dataLayer";\s*'
        r'var\s+dataLayer\s*=\s*dataLayer\s*\|\|\s*\[\];\s*</script>\s*'
        r'<!--\s*End Google Tag Manager for WordPress by gtm4wp\.com\s*-->',
        'GTM for WordPress (gtm4wp) dataLayer init'
    ),

    # 2. GTM inline script (compact)
    (
        r'<script>\s*\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?'
        r'GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\','
        r'\'GTM-[A-Z0-9]+\'\);\s*</script>',
        'Google Tag Manager script'
    ),

    # 3. GTM noscript iframe (with comments)
    (
        r'<!--\s*GTM Container placement set to footer\s*-->\s*'
        r'<!--\s*Google Tag Manager \(noscript\)\s*-->\s*'
        r'<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>'
        r'\s*</iframe>\s*</noscript>\s*'
        r'<!--\s*End Google Tag Manager \(noscript\)\s*-->',
        'GTM noscript iframe (with comments, footer)'
    ),

    # 4. GTM noscript iframe (no comments, inline in body tag)
    (
        r'<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>'
        r'[\s\S]*?</iframe>\s*</noscript>',
        'GTM noscript iframe'
    ),

    # 5. GTM form-move-tracker script
    (
        r'<script[^>]*src="https://www\.theweeknd\.com/wp-content/plugins/duracelltomi-google-tag-manager/dist/js/gtm4wp-form-move-tracker\.js[^"]*"[^>]*>\s*</script>',
        'GTM form-move-tracker'
    ),

    # 6. GTM gtag.js loader
    (
        r'<script[^>]*src="https://www\.googletagmanager\.com/gtm\.js[^"]*"[^>]*>\s*</script>',
        'GTM gtag.js loader'
    ),

    # =============================================
    # DATALAYER
    # =============================================

    # 7. dataLayer push with page_data_loaded (store)
    (
        r'<script>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];\s*'
        r'window\.dataLayer\.push\(\{[\s\S]*?\}\);\s*</script>',
        'dataLayer push (page_data_loaded)'
    ),

    # 8. Any remaining inline dataLayer scripts
    (
        r'<script(?![^>]*src)[^>]*>(?:(?!</script>).)*dataLayer(?:(?!</script>).)*</script>',
        'dataLayer inline script'
    ),

    # =============================================
    # WORDPRESS SPECIFIC (tour)
    # =============================================

    # 9. wp-emoji scripts
    (
        r'<script(?![^>]*src)[^>]*>\s*/\*\s*<!\[CDATA\[\s*\*/\s*'
        r'window\._wpemojiSettings\s*=[\s\S]*?</script>',
        'wp-emoji settings (CDATA)'
    ),

    # 10. wp-emoji settings (without CDATA)
    (
        r'<script(?![^>]*src)[^>]*>(?:(?!</script>).)*_wpemojiSettings(?:(?!</script>).)*</script>',
        'wp-emoji settings'
    ),

    # 11. Appreciation Engine / downloadJSAtOnload
    (
        r'<script[^>]*>\s*function\s+downloadJSAtOnload\(\)\s*\{[\s\S]*?'
        r'umg\.theappreciationengine\.com[\s\S]*?\}\s*'
        r'(?:if\s*\(window\.addEventListener\)[\s\S]*?window\.onload\s*=\s*downloadJSAtOnload;)\s*</script>',
        'Appreciation Engine (downloadJSAtOnload)'
    ),

    # 12. UMGECRM inline config
    (
        r'<script[^>]*id="umgecrm-frontend-script-js-extra"[^>]*>\s*'
        r'/\*\s*<!\[CDATA\[\s*\*/\s*'
        r'var\s+UMGECRM\s*=[\s\S]*?'
        r'/\*\s*\]\]>\s*\*/\s*</script>',
        'UMGECRM inline config'
    ),

    # 13. UMGECRM external script
    (
        r'<script[^>]*src="https://www\.theweeknd\.com/wp-content/plugins/umg-ecrm/[^"]*"[^>]*>\s*</script>',
        'UMGECRM external script'
    ),

    # 14. Incapsula bot protection
    (
        r'<script[^>]*src="/_Incapsula_Resource[^"]*"[^>]*>\s*</script>',
        'Incapsula bot protection'
    ),

    # =============================================
    # SHOPIFY ANALYTICS (store)
    # =============================================

    # 15. Shopify Analytics + Trekkie full block
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};[\s\S]*?</script>\s*'
        r'<script class="analytics">[\s\S]*?</script>',
        'Shopify Analytics + Trekkie'
    ),

    # 16. Shopify Analytics meta (standalone)
    (
        r'<script>\s*window\.ShopifyAnalytics\s*=\s*window\.ShopifyAnalytics\s*\|\|\s*\{\};\s*'
        r'window\.ShopifyAnalytics\.meta[\s\S]*?</script>',
        'Shopify Analytics meta'
    ),

    # 17. Shopify Trekkie script (standalone)
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
        r'<link href="https://monorail-edge\.shopifysvc\.com"[^>]*>\s*'
        r'<script>\(function\(\)\{if\s*\("sendBeacon"[\s\S]*?'
        r'handle_abandonment_event[\s\S]*?\}\(\)\);\s*</script>',
        'Shopify monorail/abandonment tracking'
    ),

    # 21. Shopify perf-kit
    (
        r'<script\s+defer\s+src="cdn/shopifycloud/perf-kit/[^"]*"[\s\S]*?>\s*</script>',
        'Shopify perf-kit'
    ),

    # 22. Shopify async loader (trackedlink, privy, rise-ai, etc.)
    (
        r'<script>\(function\(\)\s*\{\s*var\s+isLoaded\s*=\s*false;\s*'
        r'function\s+asyncLoad\(\)\s*\{[\s\S]*?'
        r'(?:trackedlink|privy|rise-ai|incartupsell|size-guides)[\s\S]*?'
        r'\}\s*\)\(\);\s*</script>',
        'Shopify async tracker loader'
    ),

    # =============================================
    # HOTJAR
    # =============================================

    # 23. Hotjar script
    (
        r'<script>\s*\(function\(h,o,t,j,a,r\)\{[\s\S]*?hotjar[\s\S]*?\}\)\(window,document,\'https://static\.hotjar\.com/c/hotjar-\',\'\.js\?sv=\'\);\s*</script>',
        'Hotjar'
    ),

    # =============================================
    # TRANSCEND / AIRGAP CONSENT
    # =============================================

    # 24. Transcend airgap script tag
    (
        r'<script[^>]*src="https://transcend-cdn\.com/cm/[^"]*airgap\.js"[^>]*>\s*</script>',
        'Transcend airgap consent'
    ),

    # =============================================
    # VICE / SDIAPI (UMG tracking)
    # =============================================

    # 25. Vice/sdiapi script
    (
        r'<script[^>]*src="https://vice-prod\.sdiapi\.com/[^"]*"[^>]*>\s*</script>',
        'Vice/sdiapi UMG tracking'
    ),

    # =============================================
    # PRIVY
    # =============================================

    # 26. Privy widget script
    (
        r'<script[^>]*src="https://widget\.privy\.com/[^"]*"[^>]*>\s*</script>',
        'Privy widget script'
    ),

    # 27. Privy CSS
    (
        r'<link[^>]*href="https://assets\.privy\.com/[^"]*"[^>]*/?>\s*',
        'Privy CSS'
    ),

    # =============================================
    # GOOGLE SITE VERIFICATION
    # =============================================

    # 28. Google site verification meta
    (
        r'<meta\s+name="google-site-verification"\s+content="[^"]*"\s*/?>',
        'Google site verification'
    ),

    # =============================================
    # PRECONNECT / DNS-PREFETCH TO TRACKERS
    # =============================================

    # 29. Preconnect to tracking domains
    (
        r'<link\s+rel="preconnect"\s+href="https://(?:'
        r'www\.googletagmanager\.com|'
        r'connect\.facebook\.net|'
        r'monorail-edge\.shopifysvc\.com|'
        r'cdn\.shopify\.com|'
        r'shop\.app'
        r')"[^>]*/?>',
        'Preconnect to tracker domain'
    ),

    # 30. DNS-prefetch to tracking domains
    (
        r'<link\s+rel="dns-prefetch"\s+href="https://(?:'
        r'www\.googletagmanager\.com|'
        r'monorail-edge\.shopifysvc\.com'
        r')"[^>]*/?>',
        'DNS-prefetch to tracker domain'
    ),

    # =============================================
    # SHOPIFY EXTERNAL SERVICES (not needed for static)
    # =============================================

    # 31. Shopify checkout preloads (xo.store/checkouts)
    (
        r'<script[^>]*src="https://xo\.store/checkouts/[^"]*"[^>]*>\s*</script>',
        'Shopify checkout preloads'
    ),

    # 32. Shop.app checkout preloads
    (
        r'<script[^>]*src="https://shop\.app/checkouts/[^"]*"[^>]*>\s*</script>',
        'Shop.app checkout preloads'
    ),

    # 33. Shopify WPM beacon script
    (
        r'<script[^>]*src="https://xo\.store/cdn/wpm/[^"]*"[^>]*>\s*</script>',
        'Shopify WPM beacon'
    ),

    # 34. Cloudflare Insights beacon
    (
        r'<script[^>]*src="https://static\.cloudflareinsights\.com/beacon[^"]*"[^>]*>\s*</script>',
        'Cloudflare Insights beacon'
    ),
]

stats = {
    'files_scanned': 0,
    'files_modified': 0,
    'patterns_removed': {}
}


def remove_trackers_from_file(filepath: Path, dry_run: bool = True) -> bool:
    """Remove tracking code from a single HTML file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return False

    original_len = len(content)
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
                    print(f"    [{name}] - {len(matches)} match(es)")
        except Exception as e:
            print(f"  Error with pattern '{name}': {e}")

    if modified:
        removed_bytes = original_len - len(content)
        if dry_run:
            print(f"  -> Would remove {removed_bytes:,} bytes")
        else:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  -> Removed {removed_bytes:,} bytes")
                return True
            except Exception as e:
                print(f"  Error writing {filepath}: {e}")
                return False

    return modified


def process_directory(directory: Path, dry_run: bool = True):
    """Process all HTML files in directory recursively."""
    html_files = sorted(directory.rglob('*.html'))
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

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files scanned: {stats['files_scanned']}")
    print(f"Files {'would be ' if dry_run else ''}modified: {stats['files_modified']}")
    print(f"\nPatterns {'that would be ' if dry_run else ''}removed:")
    for name, count in sorted(stats['patterns_removed'].items(), key=lambda x: -x[1]):
        print(f"  - {name}: {count}")

    if dry_run:
        print("\n[DRY RUN] No files were modified.")
        print("Run without --dry-run to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description='Remove tracking code from The Weeknd template (tour + store)'
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    parser.add_argument('--dir', type=str,
                        help='Custom directory to process (overrides default)')
    parser.add_argument('--tour-only', action='store_true',
                        help='Process only tour (www.theweeknd.com) files')
    parser.add_argument('--store-only', action='store_true',
                        help='Process only store (xo.store) files')
    args = parser.parse_args()

    if args.dir:
        directories = [Path(args.dir)]
    elif args.tour_only:
        directories = [THEWEEKND_DIR / "www.theweeknd.com"]
    elif args.store_only:
        directories = [THEWEEKND_DIR / "xo.store"]
    else:
        directories = [
            THEWEEKND_DIR / "www.theweeknd.com",
            THEWEEKND_DIR / "xo.store",
        ]

    for directory in directories:
        if not directory.exists():
            print(f"Error: Directory not found: {directory}")
            continue

        print(f"\n{'='*60}")
        print(f"Processing: {directory.name}")
        print(f"{'='*60}")
        process_directory(directory, dry_run=args.dry_run)

    return 0


if __name__ == '__main__':
    exit(main())
