#!/usr/bin/env node
/**
 * Puppeteer Crawler v2 — Full site downloader with JS rendering
 *
 * Downloads entire websites including all assets (HTML, CSS, JS, images, fonts).
 * Intercepts every network response and saves it to disk in the proper
 * domain/path structure (same layout as wget2).
 *
 * Features:
 *   - Intercepts & saves ALL network resources (CSS, JS, images, fonts, etc.)
 *   - Domain filter: --allowed-domains, --blocked-domains, --allowed-cdn
 *   - Reject URL patterns (--reject-regex)
 *   - Crawls across allowed domains/subdomains
 *   - Infinite scroll, "Show More" button clicking
 *   - Concurrent page crawling (--concurrency)
 *   - Graceful stop via SIGINT / SIGTERM
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');
const https = require('https');
const http = require('http');

// ═══════════════════════════════════════════════════════════════════
// CLI argument parsing
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
    maxPages:       parseInt(args[2]) || 200,
    scrollPages:    args.includes('--scroll'),
    clickShowMore:  args.includes('--click-more'),
    waitTime:       parseInt(parseArg('--wait=')) || 2000,
    depth:          parseInt(parseArg('--depth=')) || 5,
    concurrency:    parseInt(parseArg('--concurrency=')) || 3,
    allowedDomains: parseArgList('--allowed-domains='),
    blockedDomains: parseArgList('--blocked-domains='),
    allowedCdn:     parseArgList('--allowed-cdn='),
    rejectRegex:    parseArgList('--reject-regex='),
};

if (!config.url) {
    console.error('Usage: node puppeteer-crawler.js <url> <output_dir> [max_pages] [options]');
    console.error('Options:');
    console.error('  --scroll              Scroll pages to load lazy content');
    console.error('  --click-more          Click "Load More" / "Show More" buttons');
    console.error('  --wait=<ms>           Wait time after page load (default 2000)');
    console.error('  --depth=<n>           Max crawl depth (default 5)');
    console.error('  --concurrency=<n>     Concurrent pages (default 3)');
    console.error('  --allowed-domains=a,b Allowed domains (comma-separated)');
    console.error('  --blocked-domains=a,b Blocked domains (comma-separated)');
    console.error('  --allowed-cdn=a,b     Allowed CDN domains for assets');
    console.error('  --reject-regex=a,b    Reject URL regex patterns');
    process.exit(1);
}

// ═══════════════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════════════

const visitedUrls = new Set();
const savedAssets = new Set();
const pageQueue = [];           // { url, depth }
let pagesProcessed = 0;
let assetsDownloaded = 0;
let totalBytes = 0;
let stopRequested = false;

const baseUrl = new URL(config.url);

// Graceful shutdown
process.on('SIGINT',  () => { stopRequested = true; console.log('\n[STOP] SIGINT received, finishing current pages...'); });
process.on('SIGTERM', () => { stopRequested = true; console.log('\n[STOP] SIGTERM received, finishing current pages...'); });

// ═══════════════════════════════════════════════════════════════════
// Domain filtering
// ═══════════════════════════════════════════════════════════════════

function getBaseDomain(hostname) {
    const parts = hostname.split('.');
    // Handle co.uk, com.au etc.
    if (parts.length >= 3 && parts[parts.length - 2].length <= 3 && parts[parts.length - 1].length <= 3) {
        return parts.slice(-3).join('.');
    }
    if (parts.length >= 2) return parts.slice(-2).join('.');
    return hostname;
}

const baseDomain = getBaseDomain(baseUrl.hostname);

// Build reject regex patterns from CLI
const rejectPatterns = config.rejectRegex.map(p => {
    try { return new RegExp(p); } catch { return null; }
}).filter(Boolean);

function isRejectedUrl(url) {
    return rejectPatterns.some(rx => rx.test(url));
}

/**
 * Check if a domain is allowed for crawling/downloading.
 * Priority: blocked > explicit allowed > CDN > base domain match
 */
function isDomainAllowed(hostname) {
    if (!hostname) return false;
    const lower = hostname.toLowerCase();

    // 1. Blocked domains (exact or subdomain match)
    for (const b of config.blockedDomains) {
        if (lower === b || lower.endsWith('.' + b)) return false;
    }

    // 2. Explicitly allowed domains
    for (const a of config.allowedDomains) {
        if (a.startsWith('*.')) {
            const pattern = a.slice(2);
            if (lower === pattern || lower.endsWith('.' + pattern)) return true;
        } else {
            if (lower === a) return true;
        }
    }

    // 3. Allowed CDN (for assets only — fonts, libraries)
    for (const cdn of config.allowedCdn) {
        if (lower === cdn || lower.endsWith('.' + cdn)) return true;
    }

    // 4. Same base domain (covers all subdomains of the project)
    if (getBaseDomain(lower) === baseDomain) return true;

    return false;
}

/**
 * Check if a URL is allowed for page crawling (not just assets).
 * Pages are only crawled on project domains, NOT on CDN.
 */
function isPageCrawlable(url) {
    try {
        const parsed = new URL(url);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
        if (isRejectedUrl(url)) return false;
        const lower = parsed.hostname.toLowerCase();

        // Blocked
        for (const b of config.blockedDomains) {
            if (lower === b || lower.endsWith('.' + b)) return false;
        }

        // Must be on project domain (not CDN)
        for (const a of config.allowedDomains) {
            if (a.startsWith('*.')) {
                const pattern = a.slice(2);
                if (lower === pattern || lower.endsWith('.' + pattern)) return true;
            } else {
                if (lower === a) return true;
            }
        }

        // Same base domain
        return getBaseDomain(lower) === baseDomain;
    } catch {
        return false;
    }
}

/**
 * Check if a network response URL should be saved as an asset.
 */
function isAssetAllowed(url) {
    try {
        if (isRejectedUrl(url)) return false;
        const parsed = new URL(url);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
        return isDomainAllowed(parsed.hostname);
    } catch {
        return false;
    }
}

// ═══════════════════════════════════════════════════════════════════
// File saving
// ═══════════════════════════════════════════════════════════════════

function urlToFilePath(urlStr) {
    const parsed = new URL(urlStr);
    const domain = parsed.hostname;
    let pathname = decodeURIComponent(parsed.pathname);

    // Clean query params for filesystem
    // Keep query in filename for unique resources (like ?v=123)
    const query = parsed.search ? parsed.search.replace(/[<>:"|?*&=]/g, '_') : '';

    if (pathname === '/' || pathname === '') {
        pathname = '/index.html';
    }

    // If no extension and looks like a page, add .html
    const ext = path.extname(pathname).toLowerCase();
    if (!ext && !pathname.endsWith('/')) {
        pathname += '.html';
    } else if (pathname.endsWith('/')) {
        pathname += 'index.html';
    }

    // Sanitize
    pathname = pathname.replace(/[<>:"|*]/g, '_');

    const filePath = path.join(config.outputDir, domain, pathname + (query ? query : ''));
    return filePath;
}

function saveFileToDisk(filePath, buffer) {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(filePath, buffer);
        totalBytes += buffer.length;
        return true;
    } catch (err) {
        // Filename too long or invalid — skip silently
        return false;
    }
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ═══════════════════════════════════════════════════════════════════
// Page interaction helpers
// ═══════════════════════════════════════════════════════════════════

async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function autoScroll(page) {
    await page.evaluate(async () => {
        await new Promise((resolve) => {
            let totalHeight = 0;
            const distance = 500;
            const maxScrolls = 80;
            let scrollCount = 0;
            const timer = setInterval(() => {
                const scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                scrollCount++;
                if (totalHeight >= scrollHeight || scrollCount >= maxScrolls) {
                    clearInterval(timer);
                    resolve();
                }
            }, 150);
        });
    });
}

async function clickShowMoreButtons(page) {
    const selectors = [
        '[class*="load-more"]', '[class*="show-more"]', '[class*="loadmore"]',
        '[data-action="load-more"]', '[data-action="show-more"]',
        '.pagination a[rel="next"]',
        'button[class*="next"]', 'a[class*="next"]',
    ];
    // Also find by text content
    const textPatterns = ['load more', 'show more', 'see more', 'view more',
                          'more posts', 'more articles', 'next page', 'ещё', 'показать ещё'];

    for (const sel of selectors) {
        try {
            const els = await page.$$(sel);
            for (const el of els) {
                if (await el.isIntersectingViewport().catch(() => false)) {
                    await el.click().catch(() => {});
                    await sleep(config.waitTime);
                }
            }
        } catch {}
    }

    // Text-based button search
    try {
        await page.evaluate((patterns) => {
            const allButtons = [...document.querySelectorAll('button, a, [role="button"]')];
            for (const el of allButtons) {
                const txt = (el.textContent || '').trim().toLowerCase();
                if (patterns.some(p => txt.includes(p)) && el.offsetParent !== null) {
                    el.click();
                }
            }
        }, textPatterns);
        await sleep(config.waitTime);
    } catch {}
}

// ═══════════════════════════════════════════════════════════════════
// Network response interceptor — saves ALL allowed assets
// ═══════════════════════════════════════════════════════════════════

function setupResponseInterceptor(page) {
    page.on('response', async (response) => {
        try {
            const url = response.url();
            const status = response.status();

            // Skip non-success, redirects, data URIs
            if (status < 200 || status >= 300) return;
            if (url.startsWith('data:') || url.startsWith('blob:')) return;

            // Skip if already saved
            const cleanUrl = url.split('?')[0]; // de-dupe ignoring query for static assets
            if (savedAssets.has(cleanUrl)) return;

            // Check domain filter
            if (!isAssetAllowed(url)) return;

            // Don't save HTML pages here — we save rendered HTML separately
            const contentType = response.headers()['content-type'] || '';
            if (contentType.includes('text/html')) return;

            // Skip URLs that look like pages (no extension) — they'll be saved by crawlPage
            try {
                const parsedUrl = new URL(url);
                const urlExt = path.extname(parsedUrl.pathname).toLowerCase();
                if (!urlExt && !parsedUrl.pathname.endsWith('/')) {
                    // No extension = likely a page, not an asset. Skip to avoid duplicate without .html
                    return;
                }
            } catch {}

            const buffer = await response.buffer().catch(() => null);
            if (!buffer || buffer.length === 0) return;

            const filePath = urlToFilePath(url);
            if (saveFileToDisk(filePath, buffer)) {
                savedAssets.add(cleanUrl);
                assetsDownloaded++;
            }
        } catch {
            // Response may have been aborted — ignore
        }
    });
}

// ═══════════════════════════════════════════════════════════════════
// Download external images referenced in page HTML (cdn.sanity.io, etc.)
// ═══════════════════════════════════════════════════════════════════

async function downloadInlineImages(page) {
    try {
        // Extract all image URLs from DOM (img src, picture source, css background)
        const imageUrls = await page.evaluate(() => {
            const urls = new Set();
            // img[src]
            document.querySelectorAll('img[src]').forEach(img => {
                if (img.src && img.src.startsWith('http')) urls.add(img.src);
            });
            // img[data-src] (lazy loading)
            document.querySelectorAll('img[data-src]').forEach(img => {
                if (img.dataset.src && img.dataset.src.startsWith('http')) urls.add(img.dataset.src);
            });
            // source[srcset]
            document.querySelectorAll('source[srcset]').forEach(src => {
                (src.srcset || '').split(',').forEach(s => {
                    const url = s.trim().split(/\s+/)[0];
                    if (url && url.startsWith('http')) urls.add(url);
                });
            });
            // img[srcset]
            document.querySelectorAll('img[srcset]').forEach(img => {
                (img.srcset || '').split(',').forEach(s => {
                    const url = s.trim().split(/\s+/)[0];
                    if (url && url.startsWith('http')) urls.add(url);
                });
            });
            return [...urls];
        });

        let downloaded = 0;
        for (const imgUrl of imageUrls) {
            try {
                const parsed = new URL(imgUrl);
                const cleanUrl = imgUrl.split('?')[0];
                if (savedAssets.has(cleanUrl)) continue;

                // Skip already allowed domains (handled by response interceptor)
                if (isDomainAllowed(parsed.hostname)) continue;

                // Download external images (cdn.sanity.io, etc.)
                const filePath = path.join(config.outputDir, parsed.hostname, decodeURIComponent(parsed.pathname));
                if (fs.existsSync(filePath)) {
                    savedAssets.add(cleanUrl);
                    continue;
                }

                const buffer = await fetchUrl(imgUrl);
                if (buffer && buffer.length > 0) {
                    if (saveFileToDisk(filePath, buffer)) {
                        savedAssets.add(cleanUrl);
                        assetsDownloaded++;
                        downloaded++;
                    }
                }
            } catch {}
        }
        if (downloaded > 0) {
            console.log(`  → downloaded ${downloaded} external images`);
        }
    } catch {}
}

function fetchUrl(url) {
    return new Promise((resolve) => {
        const mod = url.startsWith('https') ? https : http;
        const req = mod.get(url, { timeout: 10000 }, (res) => {
            if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
                // Follow redirect
                fetchUrl(res.headers.location).then(resolve);
                return;
            }
            if (res.statusCode !== 200) { resolve(null); return; }
            const chunks = [];
            res.on('data', c => chunks.push(c));
            res.on('end', () => resolve(Buffer.concat(chunks)));
            res.on('error', () => resolve(null));
        });
        req.on('error', () => resolve(null));
        req.on('timeout', () => { req.destroy(); resolve(null); });
    });
}

// ═══════════════════════════════════════════════════════════════════
// Page crawler
// ═══════════════════════════════════════════════════════════════════

async function crawlPage(browser, url, depth) {
    if (stopRequested) return;

    const normalUrl = normalizeUrl(url);
    if (visitedUrls.has(normalUrl)) return;
    visitedUrls.add(normalUrl);

    pagesProcessed++;
    const num = pagesProcessed;
    console.log(`[${num}/${config.maxPages}] depth=${depth} ${url}`);

    let page;
    try {
        page = await browser.newPage();
        await page.setUserAgent(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        );
        await page.setViewport({ width: 1440, height: 900 });

        // Intercept responses to save assets
        setupResponseInterceptor(page);

        // Block known tracker/ad domains at request level for speed
        await page.setRequestInterception(true);
        page.on('request', (req) => {
            try {
                const reqUrl = req.url();
                const parsed = new URL(reqUrl);
                // Block explicitly blocked domains
                for (const b of config.blockedDomains) {
                    if (parsed.hostname === b || parsed.hostname.endsWith('.' + b)) {
                        req.abort('blockedbyclient').catch(() => {});
                        return;
                    }
                }
                // Block rejected URL patterns
                if (isRejectedUrl(reqUrl)) {
                    req.abort('blockedbyclient').catch(() => {});
                    return;
                }
                req.continue().catch(() => {});
            } catch {
                req.continue().catch(() => {});
            }
        });

        // Navigate
        await page.goto(url, {
            waitUntil: 'networkidle2',
            timeout: 45000
        });

        // Wait for dynamic content
        await sleep(config.waitTime);

        // Scroll to trigger lazy loading
        if (config.scrollPages) {
            await autoScroll(page);
            await sleep(1000);
        }

        // Click "Show More" buttons
        if (config.clickShowMore) {
            for (let i = 0; i < 3; i++) {
                await clickShowMoreButtons(page);
            }
        }

        // Save rendered HTML
        const html = await page.content();
        const htmlPath = urlToFilePath(url);
        saveFileToDisk(htmlPath, Buffer.from(html, 'utf-8'));
        console.log(`  ✓ saved HTML → ${path.relative(config.outputDir, htmlPath)}`);

        // Download external images referenced in HTML (cdn.sanity.io, etc.)
        await downloadInlineImages(page);

        // Extract links for further crawling
        if (depth < config.depth && pagesProcessed < config.maxPages) {
            const links = await extractLinks(page);
            let queued = 0;
            for (const link of links) {
                if (!visitedUrls.has(normalizeUrl(link)) && isPageCrawlable(link)) {
                    pageQueue.push({ url: link, depth: depth + 1 });
                    queued++;
                }
            }
            if (queued > 0) console.log(`  → queued ${queued} new links`);
        }

        console.log(`  [stats] pages=${pagesProcessed} assets=${assetsDownloaded} size=${formatSize(totalBytes)}`);

    } catch (err) {
        console.error(`  ✗ Error: ${err.message}`);
    } finally {
        if (page) await page.close().catch(() => {});
    }
}

function normalizeUrl(url) {
    try {
        const u = new URL(url);
        // Remove trailing slash for de-dup, remove hash
        let p = u.pathname.replace(/\/+$/, '') || '/';
        return u.protocol + '//' + u.host + p + u.search;
    } catch {
        return url;
    }
}

async function extractLinks(page) {
    try {
        return await page.evaluate(() => {
            const results = new Set();
            // <a href>
            document.querySelectorAll('a[href]').forEach(a => {
                if (a.href && a.href.startsWith('http')) results.add(a.href);
            });
            // <link rel="alternate" hreflang>
            document.querySelectorAll('link[hreflang]').forEach(l => {
                if (l.href && l.href.startsWith('http')) results.add(l.href);
            });
            return [...results];
        });
    } catch {
        return [];
    }
}

// ═══════════════════════════════════════════════════════════════════
// Main crawler loop with concurrency
// ═══════════════════════════════════════════════════════════════════

async function main() {
    console.log('═'.repeat(60));
    console.log('  Puppeteer Crawler v2 — Full Site Downloader');
    console.log('═'.repeat(60));
    console.log(`  URL:             ${config.url}`);
    console.log(`  Output:          ${config.outputDir}`);
    console.log(`  Max pages:       ${config.maxPages}`);
    console.log(`  Depth:           ${config.depth}`);
    console.log(`  Concurrency:     ${config.concurrency}`);
    console.log(`  Scroll:          ${config.scrollPages}`);
    console.log(`  Click more:      ${config.clickShowMore}`);
    console.log(`  Wait:            ${config.waitTime}ms`);
    if (config.allowedDomains.length)
        console.log(`  Allowed domains: ${config.allowedDomains.join(', ')}`);
    if (config.blockedDomains.length)
        console.log(`  Blocked domains: ${config.blockedDomains.slice(0, 10).join(', ')}${config.blockedDomains.length > 10 ? ` (+${config.blockedDomains.length - 10} more)` : ''}`);
    if (config.allowedCdn.length)
        console.log(`  Allowed CDN:     ${config.allowedCdn.join(', ')}`);
    console.log('═'.repeat(60));

    const browser = await puppeteer.launch({
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--window-size=1440,900',
        ]
    });

    try {
        // Seed the queue
        pageQueue.push({ url: config.url, depth: 0 });

        // Process queue with concurrency
        while ((pageQueue.length > 0 || pagesProcessed === 0) && pagesProcessed < config.maxPages && !stopRequested) {
            const batch = [];
            while (batch.length < config.concurrency && pageQueue.length > 0) {
                const item = pageQueue.shift();
                if (!visitedUrls.has(normalizeUrl(item.url))) {
                    batch.push(item);
                }
            }

            if (batch.length === 0) {
                if (pagesProcessed === 0) {
                    // First page not yet processed — wait for queue
                    await sleep(100);
                    continue;
                }
                break; // Queue empty, done
            }

            // Run batch concurrently
            await Promise.all(
                batch.map(item => crawlPage(browser, item.url, item.depth))
            );
        }

        console.log('\n' + '═'.repeat(60));
        console.log(`  ✅ Completed!`);
        console.log(`  Pages:  ${pagesProcessed}`);
        console.log(`  Assets: ${assetsDownloaded}`);
        console.log(`  Size:   ${formatSize(totalBytes)}`);
        console.log('═'.repeat(60));

    } finally {
        await browser.close();
    }
}

main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});
