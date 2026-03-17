#!/usr/bin/env python3
"""
Remove external trackers from Cardi B template index.html
Run step by step: python3 remove_cardib_trackers.py --step 1
Or all at once: python3 remove_cardib_trackers.py --all

Steps:
  1 - Facebook Pixel (connect.facebook.net signals/config)
  2 - Google Tag Manager (googletagmanager.com)
  3 - Adobe DTM/Analytics (adobedtm.com)
  4 - Snapchat Pixel (sc-static.net)
  5 - Scorecard Research (scorecardresearch.com)
  6 - TradeDesk (adsrvr.org)
  7 - TikTok Pixel (analytics.tiktok.com)
  8 - Reddit Pixel (redditstatic.com)
  9 - LinkedIn Insight (snap.licdn.com)
 10 - Pinterest Tag (s.pinimg.com)
 11 - Hotjar (static.hotjar.com)
 12 - Yahoo (s.yimg.com)
 13 - MarketingCloudFX (marketingcloudfx.com)
 14 - OneTrust/CookieLaw (cookielaw.org, onetrust, wminewmedia)
 15 - Verification meta tags (facebook-domain-verification, google-site-verification)
 16 - digitalData WMG data layer
 17 - OptanonWrapper inline
 18 - OneTrust inline style block
 19 - WMG DTM scripts (cdc.js, dtm.js, YTFns.js, toubannerupdate)
 20 - Inline tracker logic functions (all remaining)
"""

import re
import sys
import os
import shutil
import argparse

TARGET = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                      'templates', 'cardib.com.v5', 'index.html')
BACKUP = TARGET + '.backup_before_trackers'


def backup():
    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f'Backup created: {BACKUP}')
    else:
        print(f'Backup already exists: {BACKUP}')


def load():
    with open(TARGET, 'r', encoding='utf-8') as f:
        return f.read()


def save(html):
    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write(html)


def step1(html):
    """Facebook Pixel - connect.facebook.net"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*connect\.facebook\.net[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 1 (Facebook Pixel): removed {before - len(html)} chars')
    return html


def step2(html):
    """Google Tag Manager"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*googletagmanager\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 2 (Google Tag Manager): removed {before - len(html)} chars')
    return html


def step3(html):
    """Adobe DTM / Analytics"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*adobedtm\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    html = re.sub(r'<script src="//assets\.adobedtm\.com[^"]*" async=""></script>', '', html, flags=re.I)
    print(f'  Step 3 (Adobe DTM): removed {before - len(html)} chars')
    return html


def step4(html):
    """Snapchat Pixel"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*sc-static\.net[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 4 (Snapchat): removed {before - len(html)} chars')
    return html


def step5(html):
    """Scorecard Research"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*scorecardresearch\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 5 (Scorecard Research): removed {before - len(html)} chars')
    return html


def step6(html):
    """TradeDesk / adsrvr"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*adsrvr\.org[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 6 (TradeDesk): removed {before - len(html)} chars')
    return html


def step7(html):
    """TikTok Pixel"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*analytics\.tiktok\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 7 (TikTok): removed {before - len(html)} chars')
    return html


def step8(html):
    """Reddit Pixel"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*redditstatic\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 8 (Reddit): removed {before - len(html)} chars')
    return html


def step9(html):
    """LinkedIn Insight Tag"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*snap\.licdn\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 9 (LinkedIn): removed {before - len(html)} chars')
    return html


def step10(html):
    """Pinterest Tag"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*s\.pinimg\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 10 (Pinterest): removed {before - len(html)} chars')
    return html


def step11(html):
    """Hotjar"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*static\.hotjar\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 11 (Hotjar): removed {before - len(html)} chars')
    return html


def step12(html):
    """Yahoo tracking"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*s\.yimg\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 12 (Yahoo): removed {before - len(html)} chars')
    return html


def step13(html):
    """MarketingCloudFX / WebFX"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*marketingcloudfx\.com[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 13 (MarketingCloudFX): removed {before - len(html)} chars')
    return html


def step14(html):
    """OneTrust / CookieLaw / wminewmedia"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*cookielaw\.org[^"]*"[^>]*></script>', '', html, flags=re.I)
    html = re.sub(r'<script[^>]*src="[^"]*geolocation\.onetrust[^"]*"[^>]*></script>', '', html, flags=re.I)
    html = re.sub(r'<link[^>]*href="[^"]*cookielaw\.org[^"]*"[^>]*/?\s*>', '', html, flags=re.I)
    html = re.sub(r'<link[^>]*href="[^"]*wminewmedia\.com[^"]*"[^>]*/?\s*>', '', html, flags=re.I)
    print(f'  Step 14 (OneTrust/CookieLaw): removed {before - len(html)} chars')
    return html


def step15(html):
    """Verification meta tags"""
    before = len(html)
    html = re.sub(r'<meta\s+name="facebook-domain-verification"[^>]*/?\s*>', '', html, flags=re.I)
    html = re.sub(r'<meta\s+name="google-site-verification"[^>]*/?\s*>', '', html, flags=re.I)
    print(f'  Step 15 (Verification metas): removed {before - len(html)} chars')
    return html


def step16(html):
    """digitalData WMG data layer"""
    before = len(html)
    html = re.sub(r'<script[^>]*>\s*digitalData\s*=\s*\{[^<]*\}</script>', '', html, flags=re.I)
    print(f'  Step 16 (digitalData): removed {before - len(html)} chars')
    return html


def step17(html):
    """OptanonWrapper inline function"""
    before = len(html)
    html = re.sub(r'<script type="text/javascript">function OptanonWrapper\(\)[^<]*</script>', '', html, flags=re.I)
    print(f'  Step 17 (OptanonWrapper): removed {before - len(html)} chars')
    return html


def step18(html):
    """OneTrust inline style block"""
    before = len(html)
    html = re.sub(r'<style id="onetrust-style">[^<]*(?:<(?!/style>)[^<]*)*</style>', '', html, flags=re.I)
    print(f'  Step 18 (OneTrust style): removed {before - len(html)} chars')
    return html


def step19(html):
    """WMG DTM scripts (cdc.js, dtm.js, YTFns.js, toubannerupdate)"""
    before = len(html)
    html = re.sub(r'<script[^>]*src="[^"]*/mailing-list/cdc\.js"[^>]*>\s*</script>', '', html, flags=re.I)
    html = re.sub(r'<script[^>]*src="[^"]*/mailing-list/dtm\.js"[^>]*>\s*</script>', '', html, flags=re.I)
    html = re.sub(r'<script[^>]*src="[^"]*YTDTM/YTFns\.js"[^>]*>\s*</script>', '', html, flags=re.I)
    html = re.sub(r'<script[^>]*src="[^"]*toubannerupdate[^"]*"[^>]*></script>', '', html, flags=re.I)
    print(f'  Step 19 (WMG DTM scripts): removed {before - len(html)} chars')
    return html


def step20(html):
    """Inline tracker logic functions (springServe, doubleClick, tradeDesk, tiktok, linkedin, etc)"""
    before = len(html)
    # SpringServe pixel inline
    html = re.sub(r'<script>\s*function springServeLogic[\s\S]*?</script>', '', html, flags=re.I)
    # DoubleClick
    html = re.sub(r'<script>\s*function doubleClickLogic[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*function doubleClickOnEmerge[\s\S]*?</script>', '', html, flags=re.I)
    # WebFX
    html = re.sub(r'<script>\s*function webfxLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Facebook logic
    html = re.sub(r'<script>\s*function facebookLogic[\s\S]*?</script>', '', html, flags=re.I)
    # TradeDesk logic
    html = re.sub(r'<script>\s*function tradeDeskLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Ad logic
    html = re.sub(r'<script>\s*function adLogic[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*function adWordsLogic[\s\S]*?</script>', '', html, flags=re.I)
    # TikTok logic
    html = re.sub(r'<script>\s*function tiktokLogic[\s\S]*?</script>', '', html, flags=re.I)
    # LinkedIn logic
    html = re.sub(r'<script>\s*function linkedinLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Hotjar logic
    html = re.sub(r'<script>\s*function hotjarLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Snapchat logic
    html = re.sub(r'<script>\s*function snapchatLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Yahoo logic
    html = re.sub(r'<script>\s*function yahooLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Pinterest logic
    html = re.sub(r'<script>\s*function pinterestLogic[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*function executePinterestPixel[\s\S]*?</script>', '', html, flags=re.I)
    # Reddit logic
    html = re.sub(r'<script>\s*function initializeRedditScript[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*function redditLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Google Analytics logic
    html = re.sub(r'<script>\s*function googleAnalyticsLogic[\s\S]*?</script>', '', html, flags=re.I)
    # MediaMath logic
    html = re.sub(r'<script>\s*function mediaMathLogic[\s\S]*?</script>', '', html, flags=re.I)
    # Quantcast logic
    html = re.sub(r'<script>\s*function quantcastLogic[\s\S]*?</script>', '', html, flags=re.I)
    # setupAnalyticsVariables
    html = re.sub(r'<script>\s*function setupAnalyticsVariables[\s\S]*?</script>', '', html, flags=re.I)
    # isSumCalculated (fbq inline)
    html = re.sub(r'<script>\s*var isSumCalculated[\s\S]*?</script>', '', html, flags=re.I)
    # runLinkTrackingSetup
    html = re.sub(r'<script>\s*var runLinkTrackingSetup[\s\S]*?</script>', '', html, flags=re.I)
    # tdDomainBasedRules (TradeDesk rules)
    html = re.sub(r'<script>\s*var tdDomainBasedRules[\s\S]*?</script>', '', html, flags=re.I)
    # redditGlobalRules / redditDomainBasedRules / redditConditionBasedRules
    html = re.sub(r'<script>\s*//\{[^}]*\}\s*var redditGlobalRules[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*// Used for all scripts[\s\S]*?var redditDomainBasedRules[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*// Use this for scripts[\s\S]*?var redditConditionBasedRules[\s\S]*?</script>', '', html, flags=re.I)
    # executeVendorTypeTL mega-block (jshint)
    html = re.sub(r'<script>\s*/\*jshint[\s\S]*?</script>', '', html, flags=re.I)
    # _satellite._runScript1 inline
    html = re.sub(r'<script>_satellite\["_runScript1"\][\s\S]*?</script>', '', html, flags=re.I)
    # AOC = adobe.OptInCategories block
    html = re.sub(r'<script>\s*//Data Elements[\s\S]*?var AOC\s*=\s*adobe\.OptInCategories[\s\S]*?</script>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*let AOC[\s\S]*?</script>', '', html, flags=re.I)
    # retrieveOneTrust
    html = re.sub(r'<script>\s*\(function\s*\(\)\s*\{\s*function retrieveOneTrust[\s\S]*?</script>', '', html, flags=re.I)
    # const myParams
    html = re.sub(r'<script>\s*const myParams[\s\S]*?</script>', '', html, flags=re.I)
    # OneTrust consent SDK div (at very end)
    html = re.sub(r'<div id="onetrust-consent-sdk"[^>]*>[\s\S]*$', '', html, flags=re.I)
    print(f'  Step 20 (Inline tracker logic): removed {before - len(html)} chars')
    return html


ALL_STEPS = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10,
             step11, step12, step13, step14, step15, step16, step17, step18, step19, step20]


def main():
    parser = argparse.ArgumentParser(description='Remove trackers from Cardi B index.html')
    parser.add_argument('--step', type=int, help='Run specific step (1-20)')
    parser.add_argument('--all', action='store_true', help='Run all steps')
    parser.add_argument('--dry', action='store_true', help='Dry run - show what would be removed')
    parser.add_argument('--restore', action='store_true', help='Restore from backup')
    parser.add_argument('--check', action='store_true', help='Check remaining trackers')
    args = parser.parse_args()

    if args.restore:
        if os.path.exists(BACKUP):
            shutil.copy2(BACKUP, TARGET)
            print('Restored from backup')
        else:
            print('No backup found!')
        return

    if args.check:
        html = load()
        trackers = [
            ('Facebook', r'connect\.facebook\.net'),
            ('Google Tag Manager', r'googletagmanager\.com'),
            ('Adobe DTM', r'adobedtm\.com'),
            ('Snapchat', r'sc-static\.net'),
            ('Scorecard', r'scorecardresearch'),
            ('TradeDesk', r'adsrvr\.org'),
            ('TikTok', r'analytics\.tiktok\.com'),
            ('Reddit', r'redditstatic\.com'),
            ('LinkedIn', r'snap\.licdn\.com'),
            ('Pinterest', r's\.pinimg\.com'),
            ('Hotjar', r'static\.hotjar\.com'),
            ('Yahoo', r's\.yimg\.com'),
            ('MarketingCloudFX', r'marketingcloudfx\.com'),
            ('OneTrust', r'cookielaw\.org|onetrust'),
            ('FB Verification', r'facebook-domain-verification'),
            ('Google Verification', r'google-site-verification'),
            ('digitalData', r'digitalData\s*='),
            ('OptanonWrapper', r'function OptanonWrapper'),
            ('WMG DTM', r'mailing-list/cdc|mailing-list/dtm|YTDTM/YTFns|toubannerupdate'),
            ('SpringServe', r'springserve'),
            ('Demdex', r'demdex\.net'),
            ('Ad.gt', r'a\.ad\.gt'),
        ]
        found = 0
        for name, pattern in trackers:
            matches = re.findall(pattern, html, re.I)
            if matches:
                print(f'  FOUND: {name} ({len(matches)} matches)')
                found += 1
            else:
                print(f'  OK: {name} - clean')
        print(f'\nTotal: {found} trackers still present')
        return

    # Create backup before any changes
    backup()

    html = load()
    orig_size = len(html)

    if args.step:
        if 1 <= args.step <= 20:
            fn = ALL_STEPS[args.step - 1]
            html = fn(html)
            if not args.dry:
                save(html)
                print(f'Saved. Size: {orig_size} -> {len(html)}')
            else:
                print(f'[DRY RUN] Would save. Size: {orig_size} -> {len(html)}')
        else:
            print(f'Invalid step: {args.step}. Use 1-20.')
    elif args.all:
        for fn in ALL_STEPS:
            html = fn(html)
        if not args.dry:
            save(html)
            print(f'\nAll done! Size: {orig_size} -> {len(html)} (removed {orig_size - len(html)} chars)')
        else:
            print(f'\n[DRY RUN] Would save. Size: {orig_size} -> {len(html)} (would remove {orig_size - len(html)} chars)')
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
