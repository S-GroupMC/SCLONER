#!/usr/bin/env python3
"""
Remove tracking code from Metallica template HTML files.
SAFE VERSION - only removes external trackers, keeps dw.ac and CQuotient intact.

Removes:
1. Google Tag Manager (GTM) script
2. GTM noscript iframe
3. Facebook Pixel (full block with comments)
4. Marketing Cloud Analytics (igodigital)
5. Signifyd script

Does NOT remove (would break layout):
- dw.ac (Demandware Active Data) - integrated into page logic
- CQuotient - integrated into page logic
- dataLayer pushes - used by page

Usage:
    python remove_trackers_metallica.py --dry-run  # Preview changes
    python remove_trackers_metallica.py            # Apply changes
"""

import re
import argparse
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "frontend" / "src" / "templates"
METALLICA_DIR = TEMPLATES_DIR / "metallica"

# SAFE patterns - only external tracking scripts
PATTERNS = [
    # 1. Google Tag Manager script (full block)
    (
        r'<script>\(function\(w,d,s,l,i\)\{w\[l\]=w\[l\]\|\|\[\];w\[l\]\.push\(\{\'gtm\.start\':\s*new Date\(\)\.getTime\(\),event:\'gtm\.js\'\}\);var f=d\.getElementsByTagName\(s\)\[0\],\s*j=d\.createElement\(s\),dl=l!=\'dataLayer\'\?\'&l=\'\+l:\'\';j\.async=true;j\.src=\s*\'https://www\.googletagmanager\.com/gtm\.js\?id=\'\+i\+dl;f\.parentNode\.insertBefore\(j,f\);\s*\}\)\(window,document,\'script\',\'dataLayer\',\'GTM-[A-Z0-9]+\'\);</script>',
        'Google Tag Manager script'
    ),
    
    # 2. GTM noscript iframe
    (
        r'<noscript>\s*<iframe[^>]*src=[\'"]//www\.googletagmanager\.com/ns\.html\?id=[^"\']*[\'"][^>]*></iframe>\s*</noscript>',
        'GTM noscript iframe'
    ),
    
    # 3. Facebook Pixel - full block with comments
    (
        r'<!--\s*Facebook Pixel Code\s*-->\s*<script>[\s\S]*?fbq\([\'"]init[\'"][\s\S]*?</script>\s*<noscript>[\s\S]*?facebook\.com/tr[\s\S]*?</noscript>\s*<!--\s*End Facebook Pixel Code\s*-->',
        'Facebook Pixel (full block)'
    ),
    
    # 4. Marketing Cloud Analytics - full block with comments
    (
        r'<!--\s*Marketing Cloud Analytics\s*-->\s*<script[^>]*src="[^"]*igodigital\.com/collect\.js"[^>]*></script>\s*<!--\s*End Marketing Cloud Analytics\s*-->',
        'Marketing Cloud Analytics'
    ),
    
    # 5. Signifyd script
    (
        r'<script[^>]*id="sig-api"[^>]*src="[^"]*signifyd\.com[^"]*"[^>]*>\s*</script>',
        'Signifyd script'
    ),
    
    # 6. Marketing Cloud _etmc scripts (cached)
    (
        r'<!--\s*Marketing Cloud Analytics - cached\s*-->\s*<script[^>]*>\s*try\s*\{[\s\S]*?_etmc\.push[\s\S]*?\}\s*catch\s*\(e\)\s*\{[^}]*\}\s*</script>\s*<!--\s*End Marketing Cloud Analytics - cached\s*-->',
        '_etmc cached script'
    ),
    
    # 7. Marketing Cloud _etmc scripts (noncached)
    (
        r'<!--\s*Marketing Cloud Analytics - noncached\s*-->\s*<script[^>]*>\s*try\s*\{[\s\S]*?_etmc\.push[\s\S]*?\}\s*catch\s*\(e\)\s*\{[^}]*\}\s*</script>\s*<!--\s*End Marketing Cloud Analytics - noncached\s*-->',
        '_etmc noncached script'
    ),
    
    # 8. Any remaining _etmc try/catch blocks
    (
        r'<script[^>]*>\s*try\s*\{\s*_etmc\.push\([^)]*\);\s*\}\s*catch\s*\(e\)\s*\{[^}]*\}\s*</script>',
        '_etmc try/catch block'
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
    parser = argparse.ArgumentParser(description='Remove tracking code from Metallica template (SAFE)')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying files')
    parser.add_argument('--dir', type=str, help='Custom directory to process')
    args = parser.parse_args()
    
    directory = Path(args.dir) if args.dir else METALLICA_DIR
    
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return 1
    
    print(f"Removing trackers from: {directory}")
    print("SAFE MODE: Only external trackers (GTM, Facebook Pixel, igodigital)")
    process_directory(directory, dry_run=args.dry_run)
    
    return 0


if __name__ == '__main__':
    exit(main())
