#!/usr/bin/env node
/**
 * WCLoner Backend Server - Universal Template
 * Serves static files from downloaded site with domain folders
 * Structure: project_root/eagles.com/, project_root/shop.eagles.com/, etc.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.PORT || '3001', 10);
const PROJECT_DIR = __dirname;

// Directories to exclude from serving
const EXCLUDE_DIRS = new Set(['vue-app', 'node_modules', '_wcloner', '.git']);

// Рекурсивно найти первый index.html в папке
function findFirstIndexHtml(dir, maxDepth = 5, currentDepth = 0) {
  if (currentDepth > maxDepth) return null;
  try {
    // Сначала проверяем index.html в текущей папке
    const indexPath = path.join(dir, 'index.html');
    if (fs.existsSync(indexPath) && fs.statSync(indexPath).isFile()) {
      return indexPath;
    }
    // Иначе ищем в подпапках
    const items = fs.readdirSync(dir);
    for (const item of items) {
      if (item.startsWith('.') || item === 'node_modules' || item === '_next') continue;
      const itemPath = path.join(dir, item);
      if (fs.statSync(itemPath).isDirectory()) {
        const found = findFirstIndexHtml(itemPath, maxDepth, currentDepth + 1);
        if (found) return found;
      }
    }
  } catch (e) {}
  return null;
}

// Find all domain folders and detect main domain
function detectDomains() {
  const domains = [];
  let mainDomain = null;
  let mainIndexPath = null;
  
  const items = fs.readdirSync(PROJECT_DIR);
  for (const item of items) {
    if (EXCLUDE_DIRS.has(item)) continue;
    const itemPath = path.join(PROJECT_DIR, item);
    try {
      if (fs.statSync(itemPath).isDirectory() && item.includes('.')) {
        domains.push(item);
        if (!mainDomain) {
          const indexFile = findFirstIndexHtml(itemPath);
          if (indexFile) {
            mainDomain = item;
            // Сохраняем относительный путь от папки домена до index.html
            mainIndexPath = path.relative(itemPath, indexFile);
          }
        }
      }
    } catch (e) {}
  }
  
  return { domains, mainDomain, mainIndexPath };
}

const { domains, mainDomain, mainIndexPath } = detectDomains();

console.log(`[WCLoner Backend] Project: ${PROJECT_DIR}`);
console.log(`[WCLoner Backend] Domains: ${domains.join(', ') || 'none'}`);
console.log(`[WCLoner Backend] Main: ${mainDomain || 'unknown'}`);
console.log(`[WCLoner Backend] Index: ${mainIndexPath || 'not found'}`);

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.otf': 'font/otf',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.mp3': 'audio/mpeg',
  '.pdf': 'application/pdf',
  '.xml': 'application/xml',
  '.txt': 'text/plain',
  '.map': 'application/json',
};

function getContentType(filePath) {
  // Strip query params from extension detection
  const clean = filePath.replace(/\?.*$/, '').replace(/%3F.*$/i, '');
  const ext = path.extname(clean).toLowerCase();
  return MIME_TYPES[ext] || 'application/octet-stream';
}

function tryFile(filePath) {
  try {
    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      return filePath;
    }
  } catch (e) {}
  return null;
}

function findFile(urlPath) {
  // Split URL path and query
  const queryIndex = urlPath.indexOf('?');
  const basePath = queryIndex > -1 ? urlPath.substring(0, queryIndex) : urlPath;
  const queryString = queryIndex > -1 ? urlPath.substring(queryIndex) : '';
  
  // Security: prevent path traversal
  const normalized = path.normalize(basePath).replace(/\\/g, '/');
  if (normalized.includes('..')) return null;
  
  // Strategy 1: Direct path from project root (handles /eagles.com/cdn/... paths)
  let found = tryFile(path.join(PROJECT_DIR, normalized));
  if (found) return found;
  
  // Strategy 2: Try .html extension
  found = tryFile(path.join(PROJECT_DIR, normalized + '.html'));
  if (found) return found;
  
  // Strategy 3: Directory with index.html
  found = tryFile(path.join(PROJECT_DIR, normalized, 'index.html'));
  if (found) return found;
  
  // Strategy 4: If path starts with domain name, try inside that domain folder
  // e.g., /cdn/shop/... -> /eagles.com/cdn/shop/...
  if (mainDomain && !normalized.startsWith('/' + mainDomain)) {
    found = tryFile(path.join(PROJECT_DIR, mainDomain, normalized));
    if (found) return found;
    
    found = tryFile(path.join(PROJECT_DIR, mainDomain, normalized + '.html'));
    if (found) return found;
    
    found = tryFile(path.join(PROJECT_DIR, mainDomain, normalized, 'index.html'));
    if (found) return found;
  }
  
  // Strategy 5: Try other domain folders
  for (const domain of domains) {
    if (normalized.startsWith('/' + domain)) continue; // Already tried in Strategy 1
    found = tryFile(path.join(PROJECT_DIR, domain, normalized));
    if (found) return found;
  }
  
  // Strategy 6: wget2 saves query params in filenames (e.g., base.css?v=123 -> base.css?v=123)
  // Try matching files with encoded query params
  if (queryString) {
    const dir = path.dirname(path.join(PROJECT_DIR, normalized));
    const fileName = path.basename(normalized);
    try {
      if (fs.existsSync(dir)) {
        const files = fs.readdirSync(dir);
        for (const file of files) {
          if (file.startsWith(fileName) && (file.includes('%3F') || file.includes('?'))) {
            return path.join(dir, file);
          }
        }
      }
    } catch (e) {}
    
    // Also try in main domain folder
    if (mainDomain) {
      const domainDir = path.dirname(path.join(PROJECT_DIR, mainDomain, normalized));
      const domainFileName = path.basename(normalized);
      try {
        if (fs.existsSync(domainDir)) {
          const files = fs.readdirSync(domainDir);
          for (const file of files) {
            if (file.startsWith(domainFileName) && (file.includes('%3F') || file.includes('?'))) {
              return path.join(domainDir, file);
            }
          }
        }
      } catch (e) {}
    }
  }
  
  return null;
}

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url);
  
  // Remove /__raw prefix (Vite dev server proxy)
  if (urlPath.startsWith('/__raw')) {
    urlPath = urlPath.replace('/__raw', '') || '/';
  }
  
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  // Default to main domain index.html (учитываем вложенные пути типа /ko/main/index.html)
  if (urlPath === '/' || urlPath === '') {
    if (mainDomain && mainIndexPath) {
      urlPath = `/${mainDomain}/${mainIndexPath}`;
    } else if (mainDomain) {
      urlPath = `/${mainDomain}/index.html`;
    } else {
      urlPath = '/index.html';
    }
  }
  
  const filePath = findFile(urlPath);
  
  if (!filePath) {
    // Don't log noise from trackers/analytics
    if (!urlPath.includes('collect') && !urlPath.includes('produce_batch') && !urlPath.includes('.map')) {
      console.log(`[404] ${urlPath}`);
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
    return;
  }
  
  try {
    let content = fs.readFileSync(filePath);
    const mimeType = getContentType(filePath);
    
    // Rewrite absolute domain URLs to local paths in HTML
    if (mimeType.includes('text/html')) {
      let html = content.toString('utf-8');
      for (const domain of domains) {
        const escaped = domain.replace(/\./g, '\\.');
        // https://domain/path -> /domain/path
        const re = new RegExp(`(https?:)?//${escaped}/`, 'g');
        html = html.replace(re, `/${domain}/`);
      }
      content = Buffer.from(html, 'utf-8');
    }
    
    res.writeHead(200, {
      'Content-Type': mimeType,
      'Content-Length': content.length,
      'Cache-Control': 'public, max-age=3600'
    });
    res.end(content);
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Server Error');
  }
});

server.listen(PORT, () => {
  console.log(`\n[WCLoner Backend] http://localhost:${PORT}`);
  console.log(`[WCLoner Backend] Project: ${path.basename(PROJECT_DIR)}`);
  console.log(`[WCLoner Backend] Domains: ${domains.join(', ')}\n`);
});
