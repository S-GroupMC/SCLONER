#!/usr/bin/env python3
"""
Remove tracking code from template HTML files.

Supports:
- Phish template
- Ariana Grande template

Removes:
1. Google Tag Manager (GTM) script
2. Google Analytics 4 (GA4) gtag.js
3. GTM noscript iframe
4. Shopify Analytics / Trekkie
5. UMG AAL tracking (Ariana)
6. Appreciation Engine tracking (Ariana)
7. Incapsula scripts (Ariana)

Usage:
    python remove_trackers_from_phish.py --dry-run              # Preview Phish
    python remove_trackers_from_phish.py                        # Apply to Phish
    python remove_trackers_from_phish.py --template ariana --dry-run  # Preview Ariana
    python remove_trackers_from_phish.py --template ariana      # Apply to Ariana
"""

import os
import re
import argparse
from pathlib import Path

# Base directories
TEMPLATES_BASE = Path(__file__).parent.parent / "frontend" / "src" / "templates"
PHISH_TEMPLATE_DIR = TEMPLATES_BASE / "phish"
ARIANA_TEMPLATE_DIR = TEMPLATES_BASE / "Ariana_v2"

# Patterns to remove (compiled regex)
PATTERNS = [
    # 1. Google Tag Manager script (multiline) - more flexible pattern
    (
        r'<script>\s*\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];[\s\S]*?GTM-[A-Z0-9]+[\s\S]*?\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);\s*</script>\s*(?:<!--\s*End Google Tag Manager\s*-->)?',
        'Google Tag Manager script'
    ),
    
    # 1b. GTM script with newlines
    (
        r'<script>\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];w\[l\]\.push\(\{\'gtm\.start\':\s*new Date\(\)\.getTime\(\),event:\'gtm\.js\'\}\);var f=d\.getElementsByTagName\(s\)\[0\],\s*j=d\.createElement\(s\),dl=l!=\'dataLayer\'\?\'&l=\'\+l:\'\';j\.async=true;j\.src=\s*\'https://www\.googletagmanager\.com/gtm\.js\?id=\'\+i\+dl;f\.parentNode\.insertBefore\(j,f\);\s*\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);</script>\s*(?:<!--\s*End Google Tag Manager\s*-->)?',
        'Google Tag Manager script (newlines)'
    ),
    
    # 2. Google Analytics 4 (GA4) - full block with comment
    (
        r'<!--\s*Google tag \(gtag\.js\).*?-->\s*<script[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];\s*function\s+gtag\(\)\{dataLayer\.push\(arguments\);\}\s*gtag\(\'js\',\s*new\s+Date\(\)\);\s*gtag\(\'config\',\s*\'[^\']+\'\);\s*</script>',
        'Google Analytics 4 (GA4)'
    ),
    
    # 3. GA4 without comment
    (
        r'<script[^>]*async[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*<script>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];\s*function\s+gtag\(\)\{dataLayer\.push\(arguments\);\}\s*gtag\(\'js\',\s*new\s+Date\(\)\);\s*gtag\(\'config\',\s*\'[^\']+\'\);\s*</script>',
        'Google Analytics 4 (GA4) without comment'
    ),
    
    # 4. GTM noscript iframe
    (
        r'<!--\s*Google Tag Manager \(noscript\).*?-->\s*<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*></iframe>\s*</noscript>\s*(?:<!--\s*End Google Tag Manager \(noscript\)\s*-->)?',
        'GTM noscript iframe'
    ),
    
    # 5. GTM noscript without comment
    (
        r'<noscript>\s*<iframe[^>]*src="https://www\.googletagmanager\.com/ns\.html\?id=GTM-[A-Z0-9]+"[^>]*>\s*</iframe>\s*</noscript>',
        'GTM noscript iframe (no comment)'
    ),
    
    # 6. Google Analytics snippet added by Site Kit (waterwheelfoundation)
    (
        r'<!--\s*Google tag \(gtag\.js\) snippet added by Site Kit\s*-->\s*<!--\s*Google Analytics snippet added by Site Kit\s*-->\s*<script[^>]*src="https://www\.googletagmanager\.com/gtag/js\?id=[^"]*"[^>]*></script>\s*<script[^>]*id="google_gtagjs-js-after"[^>]*>\s*/\*\s*<!\[CDATA\[\s*\*/\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\];function\s+gtag\(\)\{dataLayer\.push\(arguments\);\}.*?/\*\s*\]\]>\s*\*/\s*</script>',
        'Google Analytics Site Kit'
    ),
    
    # 7. Shopify monorail/abandonment tracking
    (
        r'<link href="https://monorail-edge\.shopifysvc\.com" rel="dns-prefetch">\s*<script>\(function\(\)\{if \("sendBeacon"[\s\S]*?handle_abandonment_event[\s\S]*?\}\(\)\);</script>',
        'Shopify Abandonment Tracking'
    ),
    
    # 8. Shopify web-pixels-manager (large block)
    (
        r'<script id="web-pixels-manager-setup">[\s\S]*?</script>\s*<script>\s*window\.ShopifyAnalytics\s*=[\s\S]*?</script>\s*<script class="analytics">[\s\S]*?trekkie\.load\([\s\S]*?\);\s*</script>',
        'Shopify Analytics/Trekkie'
    ),
    
    # 9. Attentive tag
    (
        r'<!--\s*BEGIN app block:.*?attentive.*?-->\s*<script[^>]*src="https://cdn\.attn\.tv/[^"]*"[^>]*></script>\s*(?:<!--\s*END app block\s*-->)?',
        'Attentive Tag'
    ),
    
    # === ARIANA GRANDE SPECIFIC PATTERNS ===
    
    # 10. UMG AAL tracking script
    (
        r'<script[^>]*src="https://s3\.amazonaws\.com/umg-analytics/umgaal\.min\.js[^"]*"[^>]*></script>',
        'UMG AAL Analytics Script'
    ),
    
    # 11. UMG AAL WP config
    (
        r'<script[^>]*id="umg-aal-wp-js-js-extra"[^>]*>\s*/\*\s*<!\[CDATA\[\s*\*/\s*var UMGAALWP\s*=[\s\S]*?/\*\s*\]\]>\s*\*/\s*</script>',
        'UMG AAL WP Config'
    ),
    
    # 12. UMG AAL WP script (with relative paths and URL params)
    (
        r'<script[^>]*src="[^"]*umg-aal/js/umg-aal-wp\.js[^"]*"[^>]*></script>',
        'UMG AAL WP Script'
    ),
    
    # 13. onclick umgAAL tracking attributes
    (
        r'\s*onclick="umgAAL\.track\.[^"]*"',
        'UMG AAL onclick tracking'
    ),
    
    # 14. Appreciation Engine scripts (with relative paths and URL params)
    (
        r'<script[^>]*src="[^"]*appreciation-engine[^"]*"[^>]*></script>',
        'Appreciation Engine Script'
    ),
    
    # 15. Appreciation Engine config
    (
        r'<script[^>]*id="ae-wp-js-js-extra"[^>]*>\s*/\*\s*<!\[CDATA\[\s*\*/[\s\S]*?/\*\s*\]\]>\s*\*/\s*</script>',
        'Appreciation Engine Config'
    ),
    
    # 16. Incapsula resource scripts
    (
        r'<script[^>]*src="[^"]*_Incapsula_Resource[^"]*"[^>]*></script>',
        'Incapsula Script'
    ),
    
    # 17. dataLayer push for Grand Royal
    (
        r'<script[^>]*>\s*window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\]\s*window\.dataLayer\.push\(\{\s*\'waitForPageviewEvent\':\s*true,\s*\'platform\':\s*\'Grand Royal\',?\s*\}\)\s*</script>',
        'Grand Royal dataLayer'
    ),
    
    # 18. Empty GTM comments
    (
        r'<!--\s*Google Tag Manager\s*-->\s*\n*\s*<!--\s*End Google Tag Manager\s*-->',
        'Empty GTM Comments'
    ),
    
    # 19. Empty GTM noscript comments
    (
        r'<!--\s*Google Tag Manager \(noscript\)\s*-->\s*\n*\s*<!--\s*End Google Tag Manager \(noscript\)\s*-->',
        'Empty GTM noscript Comments'
    ),
]

# Statistics
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
    
    original_content = content
    modified = False
    
    for pattern, name in PATTERNS:
        try:
            regex = re.compile(pattern, re.DOTALL | re.IGNORECASE)
            matches = regex.findall(content)
            if matches:
                content = regex.sub('', content)
                modified = True
                
                # Track stats
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
    """Process all HTML files in directory recursively."""
    html_files = list(directory.rglob('*.html'))
    total = len(html_files)
    
    print(f"\nFound {total} HTML files in {directory}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLYING CHANGES'}\n")
    
    for i, filepath in enumerate(html_files, 1):
        stats['files_scanned'] += 1
        relative_path = filepath.relative_to(directory)
        
        # Skip main template files (they don't have trackers)
        if str(relative_path) in ['index.html', 'PhishTemplate.vue']:
            continue
        
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
    print("\nPatterns removed:")
    for name, count in stats['patterns_removed'].items():
        print(f"  - {name}: {count}")
    
    if dry_run:
        print("\n[DRY RUN] No files were modified. Run without --dry-run to apply changes.")


def main():
    parser = argparse.ArgumentParser(description='Remove tracking code from templates')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--dir', type=str, help='Custom directory to process')
    parser.add_argument('--template', type=str, choices=['phish', 'ariana'], default='phish',
                        help='Template to process: phish or ariana (default: phish)')
    args = parser.parse_args()
    
    # Determine directory
    if args.dir:
        directory = Path(args.dir)
    elif args.template == 'ariana':
        directory = ARIANA_TEMPLATE_DIR
    else:
        directory = PHISH_TEMPLATE_DIR
    
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1
    
    print(f"Removing trackers from: {directory}")
    print(f"Template: {args.template.upper()}")
    process_directory(directory, dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    exit(main())
