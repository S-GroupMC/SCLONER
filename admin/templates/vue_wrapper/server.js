#!/usr/bin/env node
/**
 * WCLoner Backend Server - Universal Template
 * Serves static files from downloaded site
 * Auto-detects content location in _site folder
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.PORT || '3001', 10);

// Auto-detect content directory
function findContentDir() {
  const siteDir = path.join(__dirname, '_site');
  
  // Check if _site exists
  if (!fs.existsSync(siteDir)) {
    console.error('[WCLoner] ERROR: _site folder not found!');
    return null;
  }
  
  // Check if index.html directly in _site
  if (fs.existsSync(path.join(siteDir, 'index.html'))) {
    return siteDir;
  }
  
  // Search subdirectories for index.html
  const items = fs.readdirSync(siteDir);
  for (const item of items) {
    const itemPath = path.join(siteDir, item);
    if (fs.statSync(itemPath).isDirectory()) {
      if (fs.existsSync(path.join(itemPath, 'index.html'))) {
        return itemPath;
      }
    }
  }
  
  // Fallback to _site
  return siteDir;
}

const BASE_DIR = findContentDir();

if (!BASE_DIR) {
  console.error('[WCLoner] Cannot start - no content found');
  process.exit(1);
}

console.log(`[WCLoner Backend] Serving from: ${BASE_DIR}`);

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.png': 'image/png',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
};

function getContentType(filePath) {
  const ext = path.extname(filePath.split('?')[0]).toLowerCase();
  return MIME_TYPES[ext] || 'application/octet-stream';
}

function findFile(urlPath) {
  urlPath = urlPath.split('?')[0];
  let filePath = path.join(BASE_DIR, urlPath);
  
  if (!filePath.startsWith(BASE_DIR)) return null;
  
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    return filePath;
  }
  
  if (fs.existsSync(path.join(filePath, 'index.html'))) {
    return path.join(filePath, 'index.html');
  }
  
  if (fs.existsSync(filePath + '.html')) {
    return filePath + '.html';
  }
  
  return null;
}

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url);
  
  // Remove /__raw prefix
  if (urlPath.startsWith('/__raw')) {
    urlPath = urlPath.replace('/__raw', '') || '/';
  }
  
  console.log(`[Backend] ${req.method} ${urlPath}`);
  
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  if (urlPath === '/' || urlPath === '') {
    urlPath = '/index.html';
  }
  
  const filePath = findFile(urlPath);
  
  if (!filePath) {
    res.writeHead(404, { 'Content-Type': 'text/html' });
    res.end('<h1>404 - Not Found</h1>');
    return;
  }
  
  const content = fs.readFileSync(filePath);
  const mimeType = getContentType(filePath);
  
  res.writeHead(200, {
    'Content-Type': mimeType,
    'Content-Length': content.length,
    'Cache-Control': 'public, max-age=3600'
  });
  res.end(content);
});

server.listen(PORT, () => {
  console.log(`\n[WCLoner Backend] Running on http://localhost:${PORT}`);
  console.log(`[WCLoner Backend] Serving: ${MAIN_DOMAIN}\n`);
});
