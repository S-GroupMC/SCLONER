import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

// Directories to exclude from serving
const EXCLUDE_DIRS = ['vue-app', 'node_modules', '_wcloner', '.git', '_site']

// Site content is in project root (wget creates domain folders like eagles.com/, shop.eagles.com/)
const PROJECT_DIR = path.resolve(__dirname, '..')

// Detect domain folders once at startup
function detectDomains() {
  const domains = []
  let mainDomain = null
  const items = fs.readdirSync(PROJECT_DIR)
  for (const item of items) {
    if (EXCLUDE_DIRS.includes(item)) continue
    const itemPath = path.join(PROJECT_DIR, item)
    try {
      if (fs.statSync(itemPath).isDirectory() && item.includes('.')) {
        domains.push(item)
        if (!mainDomain && fs.existsSync(path.join(itemPath, 'index.html'))) {
          mainDomain = item
        }
      }
    } catch (e) {}
  }
  return { domains, mainDomain }
}

const { domains, mainDomain } = detectDomains()

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
  '.otf': 'font/otf',
  '.mp4': 'video/mp4',
  '.mp3': 'audio/mpeg',
  '.pdf': 'application/pdf',
  '.map': 'application/json',
}

// Find a file in project directory by URL path
function findFile(urlPath) {
  const normalized = path.normalize(urlPath).replace(/\\/g, '/')
  if (normalized.includes('..')) return null

  // Strategy 1: Direct path from project root (handles /eagles.com/cdn/... paths)
  let check = path.join(PROJECT_DIR, normalized)
  if (fs.existsSync(check) && fs.statSync(check).isFile()) return check

  // Strategy 2: Try .html extension
  if (!path.extname(normalized)) {
    check = path.join(PROJECT_DIR, normalized + '.html')
    if (fs.existsSync(check) && fs.statSync(check).isFile()) return check
  }

  // Strategy 3: Directory with index.html
  check = path.join(PROJECT_DIR, normalized, 'index.html')
  if (fs.existsSync(check) && fs.statSync(check).isFile()) return check

  // Strategy 4: Prepend main domain if path doesn't start with it
  if (mainDomain && !normalized.startsWith('/' + mainDomain)) {
    check = path.join(PROJECT_DIR, mainDomain, normalized)
    if (fs.existsSync(check) && fs.statSync(check).isFile()) return check

    if (!path.extname(normalized)) {
      check = path.join(PROJECT_DIR, mainDomain, normalized + '.html')
      if (fs.existsSync(check) && fs.statSync(check).isFile()) return check
    }

    check = path.join(PROJECT_DIR, mainDomain, normalized, 'index.html')
    if (fs.existsSync(check) && fs.statSync(check).isFile()) return check
  }

  // Strategy 5: Try other domain folders
  for (const domain of domains) {
    if (normalized.startsWith('/' + domain)) continue
    check = path.join(PROJECT_DIR, domain, normalized)
    if (fs.existsSync(check) && fs.statSync(check).isFile()) return check
  }

  return null
}

// Serve a found file with correct MIME type
function serveFile(filePath, res) {
  const ext = path.extname(filePath.replace(/\?.*$/, '')).toLowerCase()
  const contentType = MIME_TYPES[ext] || 'application/octet-stream'
  const content = fs.readFileSync(filePath)
  res.setHeader('Content-Type', contentType)
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Cache-Control', 'public, max-age=3600')
  res.end(content)
}

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'serve-site',
      configureServer(server) {
        // Middleware 0: Redirect internal page links to Vue wrapper
        // When user clicks /pages/home in iframe, it escapes to top level
        // Redirect to /?page=pages/home.html so Vue wrapper handles it
        server.middlewares.use((req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]

          // Skip system paths, assets, and /__raw
          if (urlPath === '/' || urlPath.startsWith('/@') || urlPath.startsWith('/src/') ||
              urlPath.startsWith('/node_modules/') || urlPath.startsWith('/__raw')) {
            return next()
          }

          const ext = path.extname(urlPath).toLowerCase()

          // Skip static assets (css, js, images, fonts)
          if (ext && ext !== '.html' && MIME_TYPES[ext]) {
            return next()
          }

          // Skip domain-prefixed paths (these are assets like /eagles.com/cdn/...)
          const isDomainPath = domains.some(d => urlPath.startsWith('/' + d + '/'))
          if (isDomainPath) {
            return next()
          }

          // Check if this path resolves to an HTML file in any domain folder
          const referer = req.headers.referer || ''
          const isFromIframe = referer.includes('/__raw')

          // For HTML page paths (no ext or .html): if file exists, serve via redirect
          if (!ext || ext === '.html') {
            const filePath = findFile(urlPath)
            if (filePath && filePath.endsWith('.html')) {
              if (isFromIframe) {
                // Request from iframe - serve file directly (internal navigation)
                serveFile(filePath, res)
                return
              } else {
                // Top-level navigation - redirect to Vue wrapper
                const pagePath = urlPath.replace(/^\//, '').replace(/\.html$/, '') + '.html'
                res.writeHead(302, { Location: '/?page=' + encodeURIComponent(pagePath) })
                res.end()
                return
              }
            }
          }

          next()
        })

        // Middleware 1: Serve site assets (domain paths AND subdomain-relative paths)
        // Handles /eagles.com/cdn/... AND /cdn/shop/... (without domain prefix)
        server.middlewares.use((req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]

          // Skip Vite internal paths and Vue app paths
          if (urlPath.startsWith('/@') || urlPath.startsWith('/src/') ||
              urlPath.startsWith('/node_modules/') || urlPath === '/') {
            return next()
          }

          // Check if path starts with domain folder
          const isDomainPath = domains.some(d => urlPath.startsWith('/' + d + '/'))

          // Check if path has a static file extension (css, js, images, fonts, etc.)
          const ext = path.extname(urlPath).toLowerCase()
          const isAsset = ext && ext !== '.html' && MIME_TYPES[ext]

          if (!isDomainPath && !isAsset) return next()

          const filePath = findFile(urlPath)
          if (filePath) {
            serveFile(filePath, res)
          } else {
            next()
          }
        })

        // Middleware 2: /__raw prefix for iframe content
        server.middlewares.use('/__raw', (req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]

          // Default to index.html in main domain folder
          let resolvedPath = urlPath
          if (urlPath === '/' || urlPath === '') {
            resolvedPath = mainDomain ? `/${mainDomain}/index.html` : '/index.html'
          }

          const filePath = findFile(resolvedPath)
          if (filePath) {
            serveFile(filePath, res)
          } else {
            res.statusCode = 404
            res.end('Not found: ' + urlPath)
          }
        })
      }
    }
  ],
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  }
})
