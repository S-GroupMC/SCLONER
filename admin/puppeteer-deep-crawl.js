#!/usr/bin/env node
/**
 * Puppeteer Deep Crawler — discovers SPA routes by clicking on interactive elements.
 * Designed for Next.js / React sites where navigation uses onClick, not <a href>.
 *
 * Phase 1: Discover all routes by navigating menus and clicking items
 * Phase 2: Download each discovered page with all assets
 *
 * Usage: node puppeteer-deep-crawl.js <url> <output_dir> [options]
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

// ═══════════════════════════════════════════════════════════════════
// CLI
// ═══════════════════════════════════════════════════════════════════

function parseArg(prefix) {
    const a = process.argv.find(x => x.startsWith(prefix));
    return a ? a.slice(prefix.length) : null;
}
function parseArgList(prefix) {
    const v = parseArg(prefix);
    return v ? v.split(',').map(s => s.trim()).filter(Boolean) : [];
}

const args = process.argv.slice(2);
const config = {
    url:            args[0],
    outputDir:      args[1] || './output',
    maxPages:       parseInt(parseArg('--max-pages=')) || 500,
    waitTime:       parseInt(parseArg('--wait=')) || 2500,
    concurrency:    parseInt(parseArg('--concurrency=')) || 2,
    blockedDomains: parseArgList('--blocked-domains='),
    allowedCdn:     parseArgList('--allowed-cdn='),
    rejectRegex:    parseArgList('--reject-regex='),
    lang:           parseArg('--lang=') || 'ko',
};

if (!config.url) {
    console.error('Usage: node puppeteer-deep-crawl.js <url> <output_dir> [options]');
    console.error('  --max-pages=N       Max pages to download (default 500)');
    console.error('  --wait=ms           Wait after navigation (default 2500)');
    console.error('  --concurrency=N     Parallel downloads in phase 2 (default 2)');
    console.error('  --blocked-domains=  Comma-separated blocked domains');
    console.error('  --allowed-cdn=      Comma-separated allowed CDN domains');
    console.error('  --reject-regex=     Comma-separated reject URL patterns');
    console.error('  --lang=ko           Language prefix (default ko)');
    process.exit(1);
}

// ═══════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════

const baseUrl = new URL(config.url);
const baseDomain = getBaseDomain(baseUrl.hostname);
const discoveredUrls = new Set();
const savedAssets = new Set();
let assetsDownloaded = 0;
let totalBytes = 0;
let stopRequested = false;

process.on('SIGINT',  () => { stopRequested = true; console.log('\n[STOP] Finishing...'); });
process.on('SIGTERM', () => { stopRequested = true; });

// Reject patterns
const rejectPatterns = config.rejectRegex.map(p => {
    try { return new RegExp(p); } catch { return null; }
}).filter(Boolean);

function isRejectedUrl(url) {
    return rejectPatterns.some(rx => rx.test(url));
}

function getBaseDomain(hostname) {
    const parts = hostname.split('.');
    if (parts.length >= 3 && parts[parts.length - 2].length <= 3 && parts[parts.length - 1].length <= 3)
        return parts.slice(-3).join('.');
    if (parts.length >= 2) return parts.slice(-2).join('.');
    return hostname;
}

function isDomainAllowed(hostname) {
    if (!hostname) return false;
    const lower = hostname.toLowerCase();
    for (const b of config.blockedDomains) {
        if (lower === b || lower.endsWith('.' + b)) return false;
    }
    for (const cdn of config.allowedCdn) {
        if (lower === cdn || lower.endsWith('.' + cdn)) return true;
    }
    return getBaseDomain(lower) === baseDomain;
}

function isAssetAllowed(url) {
    try {
        if (isRejectedUrl(url)) return false;
        const parsed = new URL(url);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
        return isDomainAllowed(parsed.hostname);
    } catch { return false; }
}

// ═══════════════════════════════════════════════════════════════════
// File saving
// ═══════════════════════════════════════════════════════════════════

function urlToFilePath(urlStr) {
    const parsed = new URL(urlStr);
    let pathname = decodeURIComponent(parsed.pathname);
    const query = parsed.search ? parsed.search.replace(/[<>:"|?*&=]/g, '_') : '';
    if (pathname === '/' || pathname === '') pathname = '/index.html';
    const ext = path.extname(pathname).toLowerCase();
    if (!ext && !pathname.endsWith('/')) pathname += '/index.html';
    else if (pathname.endsWith('/')) pathname += 'index.html';
    pathname = pathname.replace(/[<>:"|*]/g, '_');
    return path.join(config.outputDir, parsed.hostname, pathname + query);
}

function saveFile(filePath, buffer) {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(filePath, buffer);
        totalBytes += buffer.length;
        return true;
    } catch { return false; }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ═══════════════════════════════════════════════════════════════════
// Network interceptor — saves assets
// ═══════════════════════════════════════════════════════════════════

function setupInterceptor(page) {
    page.on('response', async (response) => {
        try {
            const url = response.url();
            if (response.status() < 200 || response.status() >= 300) return;
            if (url.startsWith('data:') || url.startsWith('blob:')) return;
            const cleanUrl = url.split('?')[0];
            if (savedAssets.has(cleanUrl)) return;
            if (!isAssetAllowed(url)) return;
            const ct = response.headers()['content-type'] || '';
            if (ct.includes('text/html')) return;
            const buffer = await response.buffer().catch(() => null);
            if (!buffer || buffer.length === 0) return;
            const filePath = urlToFilePath(url);
            if (saveFile(filePath, buffer)) {
                savedAssets.add(cleanUrl);
                assetsDownloaded++;
            }
        } catch {}
    });
}

// ═══════════════════════════════════════════════════════════════════
// Phase 1: Discover ALL routes by navigating the SPA
// ═══════════════════════════════════════════════════════════════════

async function discoverRoutes(browser) {
    console.log('\n╔══════════════════════════════════════════════════════╗');
    console.log('║  Phase 1: Discovering SPA routes                    ║');
    console.log('╚══════════════════════════════════════════════════════╝\n');

    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36');
    await page.setViewport({ width: 1440, height: 900 });

    // Block trackers
    await page.setRequestInterception(true);
    page.on('request', (req) => {
        try {
            const h = new URL(req.url()).hostname;
            for (const b of config.blockedDomains) {
                if (h === b || h.endsWith('.' + b)) { req.abort('blockedbyclient').catch(()=>{}); return; }
            }
            req.continue().catch(()=>{});
        } catch { req.continue().catch(()=>{}); }
    });

    // Monitor URL changes
    page.on('framenavigated', async (frame) => {
        if (frame === page.mainFrame()) {
            const url = page.url();
            if (url.startsWith('http') && isDomainAllowed(new URL(url).hostname)) {
                discoveredUrls.add(url);
            }
        }
    });

    // Navigate to start URL
    console.log(`[Discovery] Starting at: ${config.url}`);
    await page.goto(config.url, { waitUntil: 'networkidle2', timeout: 45000 });
    await sleep(config.waitTime);
    discoveredUrls.add(page.url());

    // Step 1: Find all main navigation links
    console.log('[Discovery] Scanning main navigation...');
    const navLinks = await page.evaluate((lang) => {
        const links = new Set();
        // Get all clickable elements in nav
        document.querySelectorAll('nav a, header a, [class*="nav"] a, [class*="menu"] a, [class*="Nav"] a, [class*="Menu"] a').forEach(a => {
            if (a.href && a.href.startsWith('http')) links.add(a.href);
        });
        // Get all <a> tags on page
        document.querySelectorAll('a[href]').forEach(a => {
            if (a.href && a.href.startsWith('http')) links.add(a.href);
        });
        return [...links];
    }, config.lang);

    for (const link of navLinks) {
        try {
            const u = new URL(link);
            if (isDomainAllowed(u.hostname)) discoveredUrls.add(link);
        } catch {}
    }
    console.log(`  Found ${navLinks.length} navigation links`);

    // Step 2: Navigate to each top-level section and discover sub-routes by clicking
    const sections = [...discoveredUrls].filter(u => {
        try { return new URL(u).pathname.split('/').filter(Boolean).length <= 3; } catch { return false; }
    });

    console.log(`[Discovery] Exploring ${sections.length} sections for sub-routes...`);

    for (const sectionUrl of sections) {
        if (stopRequested) break;
        const before = discoveredUrls.size;
        try {
            console.log(`  → ${sectionUrl}`);
            await page.goto(sectionUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(config.waitTime);

            // Scroll to load all content
            await autoScroll(page);
            await sleep(1000);

            // Extract links after full render
            const pageLinks = await page.evaluate(() => {
                const results = new Set();
                document.querySelectorAll('a[href]').forEach(a => {
                    if (a.href && a.href.startsWith('http')) results.add(a.href);
                });
                return [...results];
            });
            for (const link of pageLinks) {
                try {
                    if (isDomainAllowed(new URL(link).hostname)) discoveredUrls.add(link);
                } catch {}
            }

            // Click on list items, cards, grid items to discover detail pages
            const clickableCount = await discoverByClicking(page);
            if (clickableCount > 0) {
                console.log(`    clicked ${clickableCount} items → ${discoveredUrls.size - before} new routes`);
            }

        } catch (err) {
            console.log(`    ✗ ${err.message}`);
        }
    }

    // Step 3: Check for discography detail pages by clicking on album covers/cards
    const discographyUrls = [...discoveredUrls].filter(u => u.includes('/discography'));
    if (discographyUrls.length > 0) {
        console.log(`\n[Discovery] Deep-scanning ${discographyUrls.length} discography pages...`);
        for (const dUrl of discographyUrls) {
            if (stopRequested) break;
            if (dUrl.includes('/detail/')) continue; // Already a detail page
            try {
                console.log(`  → ${dUrl}`);
                await page.goto(dUrl, { waitUntil: 'networkidle2', timeout: 30000 });
                await sleep(config.waitTime);
                await autoScroll(page);
                await sleep(1500);

                // Click every album/card/item
                const found = await discoverByClicking(page);
                console.log(`    clicked ${found} items → found ${discoveredUrls.size} total routes`);
            } catch (err) {
                console.log(`    ✗ ${err.message}`);
            }
        }
    }

    // Step 3b: Also check tour pages
    const tourUrls = [...discoveredUrls].filter(u => u.includes('/tour'));
    if (tourUrls.length > 0) {
        console.log(`\n[Discovery] Deep-scanning ${tourUrls.length} tour pages...`);
        for (const tUrl of tourUrls) {
            if (stopRequested) break;
            if (tUrl.includes('/detail/')) continue;
            try {
                console.log(`  → ${tUrl}`);
                await page.goto(tUrl, { waitUntil: 'networkidle2', timeout: 30000 });
                await sleep(config.waitTime);
                await autoScroll(page);
                await sleep(1500);
                const found = await discoverByClicking(page);
                console.log(`    clicked ${found} items → found ${discoveredUrls.size} total routes`);
            } catch (err) {
                console.log(`    ✗ ${err.message}`);
            }
        }
    }

    await page.close();

    // Dedup and sort
    const allUrls = [...discoveredUrls].sort();
    console.log(`\n[Discovery] Total unique routes: ${allUrls.length}`);
    for (const u of allUrls) {
        console.log(`  ${new URL(u).pathname}`);
    }

    return allUrls;
}

async function discoverByClicking(page) {
    let found = 0;
    const startUrl = page.url();

    // Find clickable cards/items that might navigate to detail pages
    const clickableSelectors = [
        '[class*="item"]', '[class*="card"]', '[class*="album"]', '[class*="disc"]',
        '[class*="thumb"]', '[class*="cover"]', '[class*="post"]', '[class*="article"]',
        '[class*="list"] > div', '[class*="grid"] > div', '[class*="swiper"] .swiper-slide',
        'li[class]', '[role="listitem"]', '[data-id]', '[data-slug]',
        '[class*="Item"]', '[class*="Card"]', '[class*="Album"]', '[class*="Disc"]',
        '[class*="Thumb"]', '[class*="Cover"]', '[class*="Tour"]',
    ];

    for (const sel of clickableSelectors) {
        try {
            const elements = await page.$$(sel);
            for (let i = 0; i < Math.min(elements.length, 50); i++) {
                if (stopRequested) return found;
                try {
                    const isVisible = await elements[i].isIntersectingViewport().catch(() => false);
                    if (!isVisible) continue;

                    // Click and wait for potential navigation
                    await elements[i].click().catch(() => {});
                    await sleep(800);

                    const newUrl = page.url();
                    if (newUrl !== startUrl && newUrl.startsWith('http')) {
                        const u = new URL(newUrl);
                        if (isDomainAllowed(u.hostname) && !discoveredUrls.has(newUrl)) {
                            discoveredUrls.add(newUrl);
                            found++;
                        }
                        // Go back to continue clicking
                        await page.goBack({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
                        await sleep(800);
                        // Re-scroll to load items again
                        await autoScroll(page);
                        await sleep(500);
                    }
                } catch {}
            }
        } catch {}
    }

    return found;
}

async function autoScroll(page) {
    await page.evaluate(async () => {
        await new Promise((resolve) => {
            let total = 0; const dist = 500; let count = 0;
            const timer = setInterval(() => {
                window.scrollBy(0, dist);
                total += dist; count++;
                if (total >= document.body.scrollHeight || count >= 60) {
                    clearInterval(timer); resolve();
                }
            }, 120);
        });
    });
}

// ═══════════════════════════════════════════════════════════════════
// Phase 2: Download ALL discovered pages with assets
// ═══════════════════════════════════════════════════════════════════

async function downloadPages(browser, urls) {
    console.log('\n╔══════════════════════════════════════════════════════╗');
    console.log('║  Phase 2: Downloading pages and assets              ║');
    console.log('╚══════════════════════════════════════════════════════╝\n');

    let downloaded = 0;

    // Process in batches
    for (let i = 0; i < urls.length; i += config.concurrency) {
        if (stopRequested) break;
        const batch = urls.slice(i, i + config.concurrency);
        await Promise.all(batch.map(url => downloadPage(browser, url, ++downloaded, urls.length)));
    }

    return downloaded;
}

async function downloadPage(browser, url, num, total) {
    let page;
    try {
        page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36');
        await page.setViewport({ width: 1440, height: 900 });

        setupInterceptor(page);

        await page.setRequestInterception(true);
        page.on('request', (req) => {
            try {
                const h = new URL(req.url()).hostname;
                for (const b of config.blockedDomains) {
                    if (h === b || h.endsWith('.' + b)) { req.abort('blockedbyclient').catch(()=>{}); return; }
                }
                if (isRejectedUrl(req.url())) { req.abort('blockedbyclient').catch(()=>{}); return; }
                req.continue().catch(()=>{});
            } catch { req.continue().catch(()=>{}); }
        });

        console.log(`[${num}/${total}] ${url}`);
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
        await sleep(config.waitTime);
        await autoScroll(page);
        await sleep(1000);

        // Save rendered HTML
        const html = await page.content();
        const filePath = urlToFilePath(url);
        saveFile(filePath, Buffer.from(html, 'utf-8'));
        console.log(`  ✓ ${path.relative(config.outputDir, filePath)}  [assets=${assetsDownloaded} size=${formatSize(totalBytes)}]`);

    } catch (err) {
        console.log(`  ✗ ${err.message}`);
    } finally {
        if (page) await page.close().catch(() => {});
    }
}

// ═══════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════

async function main() {
    console.log('═'.repeat(60));
    console.log('  Puppeteer Deep Crawler — SPA Route Discovery');
    console.log('═'.repeat(60));
    console.log(`  URL:    ${config.url}`);
    console.log(`  Output: ${config.outputDir}`);
    console.log(`  Lang:   ${config.lang}`);
    console.log('═'.repeat(60));

    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
               '--disable-gpu', '--window-size=1440,900']
    });

    try {
        // Phase 1: Discover routes
        const allUrls = await discoverRoutes(browser);

        if (allUrls.length === 0) {
            console.log('No routes discovered!');
            return;
        }

        // Phase 2: Download all pages
        const downloaded = await downloadPages(browser, allUrls);

        console.log('\n' + '═'.repeat(60));
        console.log(`  ✅ Deep Crawl Complete!`);
        console.log(`  Routes discovered: ${allUrls.length}`);
        console.log(`  Pages downloaded:  ${downloaded}`);
        console.log(`  Assets saved:      ${assetsDownloaded}`);
        console.log(`  Total size:        ${formatSize(totalBytes)}`);
        console.log('═'.repeat(60));

    } finally {
        await browser.close();
    }
}

main().catch(err => {
    console.error('Fatal:', err);
    process.exit(1);
});
