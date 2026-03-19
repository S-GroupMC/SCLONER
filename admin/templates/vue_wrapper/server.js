#!/usr/bin/env node
/**
 * WCLoner Backend Server - Universal Template
 * Serves static files from downloaded site
 * Works directly with project folder (no _site duplication)
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.PORT || '3001', 10);

// Directories to exclude from serving
const EXCLUDE_DIRS = ['vue-app', 'node_modules', '_wcloner', '.git'];
const EXCLUDE_FILES = ['backend-server.js', 'package.json', 'package-lock.json', 'README.md', 'README-VUE.md'];

// Auto-detect content directory
function findContentDir() {
  const projectDir = __dirname;
  
  // Check if index.html directly in project root
  if (fs.existsSync(path.join(projectDir, 'index.html'))) {
    return projectDir;
  }
  
  // Search subdirectories for index.html (domain folders like eagles.com/)
  const items = fs.readdirSync(projectDir);
  for (const item of items) {
    if (EXCLUDE_DIRS.includes(item)) continue;
    const itemPath = path.join(projectDir, item);
    if (fs.statSync(itemPath).isDirectory()) {
      if (fs.existsSync(path.join(itemPath, 'index.html'))) {
        return itemPath;
      }
    }
  }
  
  // Fallback to project root
  return projectDir;
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
  const queryIndex = urlPath.indexOf('?');
  const basePath = queryIndex > -1 ? urlPath.substring(0, queryIndex) : urlPath;
  const queryPart = queryIndex > -1 ? urlPath.substring(queryIndex) : '';
  
  let filePath = path.join(BASE_DIR, basePath);
  
  if (!filePath.startsWith(BASE_DIR)) return null;
  
  // Direct file exists
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    return filePath;
  }
  
  // Try with .html extension (for paths like /pages/home -> /pages/home.html)
  if (fs.existsSync(filePath + '.html')) {
    return filePath + '.html';
  }
  
  // Directory with index.html
  if (fs.existsSync(path.join(filePath, 'index.html'))) {
    return path.join(filePath, 'index.html');
  }
  
  // Try with URL-encoded query params in filename (wget2 saves files this way)
  if (queryPart) {
    const dir = path.dirname(filePath);
    const fileName = path.basename(filePath);
    
    if (fs.existsSync(dir)) {
      const files = fs.readdirSync(dir);
      for (const file of files) {
        // Match files like "base.css%3Fv=123.css" when requesting "base.css?v=123"
        if (file.startsWith(fileName) && file.includes('%3F')) {
          return path.join(dir, file);
        }
      }
    }
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
  
  let content = fs.readFileSync(filePath);
  const mimeType = getContentType(filePath);
  
  // Rewrite external URLs to local for HTML files
  if (mimeType.includes('text/html')) {
    let html = content.toString('utf-8');
    // Get domain from project folder name (e.g., /downloads/eagles.com -> eagles.com)
    const projectDirName = path.basename(path.dirname(BASE_DIR === __dirname ? BASE_DIR : path.dirname(BASE_DIR)));
    const domainMatch = projectDirName.match(/^([a-z0-9-]+\.[a-z]{2,})/i);
    if (domainMatch) {
      const domain = domainMatch[1];
      // Replace //domain/ and https://domain/ with local /
      const domainRegex = new RegExp(`(https?:)?//${domain.replace(/\./g, '\\.')}/`, 'g');
      html = html.replace(domainRegex, '/');
    }
    content = Buffer.from(html, 'utf-8');
  }
  
  res.writeHead(200, {
    'Content-Type': mimeType,
    'Content-Length': content.length,
    'Cache-Control': 'public, max-age=3600'
  });
  res.end(content);
});

server.listen(PORT, () => {
  console.log(`\n[WCLoner Backend] Running on http://localhost:${PORT}`);
  console.log(`[WCLoner Backend] Serving: ${path.basename(BASE_DIR)}\n`);
});
