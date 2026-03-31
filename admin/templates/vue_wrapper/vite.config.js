import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'
import https from 'https'

// Directories to exclude from serving
const EXCLUDE_DIRS = ['vue-app', 'node_modules', '_wcloner', '.git', '_site']

// Site content is in project root (wget creates domain folders like eagles.com/, shop.eagles.com/)
const PROJECT_DIR = path.resolve(__dirname, '..')

// Рекурсивно найти первый index.html в папке
function findFirstIndexHtml(dir, maxDepth = 5, currentDepth = 0) {
  if (currentDepth > maxDepth) return null
  try {
    const indexPath = path.join(dir, 'index.html')
    if (fs.existsSync(indexPath) && fs.statSync(indexPath).isFile()) return indexPath
    const items = fs.readdirSync(dir)
    for (const item of items) {
      if (item.startsWith('.') || item === 'node_modules' || item === '_next') continue
      const itemPath = path.join(dir, item)
      if (fs.statSync(itemPath).isDirectory()) {
        const found = findFirstIndexHtml(itemPath, maxDepth, currentDepth + 1)
        if (found) return found
      }
    }
  } catch (e) {}
  return null
}

// Detect domain folders once at startup
function detectDomains() {
  const domains = []
  let mainDomain = null
  let mainIndexPath = null
  const items = fs.readdirSync(PROJECT_DIR)
  for (const item of items) {
    if (EXCLUDE_DIRS.includes(item)) continue
    const itemPath = path.join(PROJECT_DIR, item)
    try {
      if (fs.statSync(itemPath).isDirectory() && item.includes('.')) {
        domains.push(item)
        if (!mainDomain) {
          const indexFile = findFirstIndexHtml(itemPath)
          if (indexFile) {
            mainDomain = item
            mainIndexPath = path.relative(itemPath, indexFile)
          }
        }
      }
    } catch (e) {}
  }
  return { domains, mainDomain, mainIndexPath }
}

const { domains, mainDomain, mainIndexPath } = detectDomains()

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
  // Strip query params for file lookup
  const queryIndex = urlPath.indexOf('?')
  let basePath = queryIndex > -1 ? urlPath.substring(0, queryIndex) : urlPath
  
  // Двойное декодирование для путей типа /public%2FalbumThumbnail%2F...
  if (basePath.includes('%2F') || basePath.includes('%2f')) {
    try {
      basePath = decodeURIComponent(basePath)
    } catch (e) {}
  }
  
  // Исправление дублирования языкового префикса /ko/ko/ -> /ko/
  basePath = basePath.replace(/^\/([a-z]{2})\/\1\//, '/$1/')
  
  const normalized = path.normalize(basePath).replace(/\\/g, '/')
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
  let content = fs.readFileSync(filePath)
  
  // Переписываем hardcoded доменные URL в JS файлах на относительные
  // https://ibighit.com/api/... → /api/... (запросы пойдут через наш прокси)
  if (mainDomain && (ext === '.js' || ext === '.mjs')) {
    let text = content.toString('utf-8')
    const escaped = mainDomain.replace(/\./g, '\\.')
    const re = new RegExp('https?://' + escaped, 'g')
    if (re.test(text)) {
      text = text.replace(re, '')
      content = Buffer.from(text, 'utf-8')
    }
  }
  
  res.setHeader('Content-Type', contentType)
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Cache-Control', 'public, max-age=3600')
  res.end(content)
}

// === Reverse Proxy: динамический контент с оригинального сервера ===
function proxyToOrigin(domain, req, res, overridePath, rawPrefix) {
  const proxyPath = overridePath || req.url
  const targetUrl = `https://${domain}${proxyPath}`
  
  console.log(`[Proxy] ${proxyPath} -> ${targetUrl}`)
  
  const parsed = new URL(targetUrl)
  // Передаём заголовки клиента (x-access-site-seq, authorization и др.)
  const fwdHeaders = {
    'host': parsed.hostname,
    'user-agent': req.headers['user-agent'] || 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'accept': req.headers['accept'] || '*/*',
    'accept-language': req.headers['accept-language'] || 'ko,en;q=0.9',
    'referer': `https://${parsed.hostname}/`,
    'origin': `https://${parsed.hostname}`,
  }
  // Пробрасываем важные заголовки от клиента
  for (const h of ['x-access-site-seq', 'authorization', 'content-type', 'cookie']) {
    if (req.headers[h]) fwdHeaders[h] = req.headers[h]
  }
  const options = {
    hostname: parsed.hostname,
    port: 443,
    path: parsed.pathname + parsed.search,
    method: req.method || 'GET',
    headers: fwdHeaders
  }
  
  const proxyReq = https.request(options, (proxyRes) => {
    const resHeaders = {
      'access-control-allow-origin': '*',
    }
    for (const h of ['content-type', 'content-length', 'cache-control', 'etag', 'last-modified']) {
      if (proxyRes.headers[h]) resHeaders[h] = proxyRes.headers[h]
    }
    if (proxyRes.headers['location']) {
      let loc = proxyRes.headers['location']
        .replace(new RegExp(`https?://${domain.replace(/\./g, '\\.')}`, 'g'), '')
      // Сохраняем контекст /__raw при редиректах из iframe
      if (rawPrefix && loc.startsWith('/')) loc = rawPrefix + loc
      resHeaders['location'] = loc
    }
    
    // Для JS файлов: буферизуем и переписываем доменные URL на относительные
    const proxyContentType = proxyRes.headers['content-type'] || ''
    const isJS = proxyContentType.includes('javascript') || proxyPath.match(/\.js(\?|$)/)
    
    if (isJS && domain) {
      const chunks = []
      proxyRes.on('data', chunk => chunks.push(chunk))
      proxyRes.on('end', () => {
        let body = Buffer.concat(chunks).toString('utf-8')
        const escaped = domain.replace(/\./g, '\\.')
        body = body.replace(new RegExp('https?://' + escaped, 'g'), '')
        const buf = Buffer.from(body, 'utf-8')
        resHeaders['content-length'] = buf.length.toString()
        res.writeHead(proxyRes.statusCode, resHeaders)
        res.end(buf)
      })
    } else {
      res.writeHead(proxyRes.statusCode, resHeaders)
      proxyRes.pipe(res)
    }
  })
  
  proxyReq.on('error', (err) => {
    console.log(`[Proxy Error] ${err.message}`)
    if (!res.headersSent) {
      res.statusCode = 502
      res.end('Proxy Error')
    }
  })
  
  proxyReq.setTimeout(15000, () => {
    proxyReq.destroy()
    if (!res.headersSent) {
      res.statusCode = 504
      res.end('Proxy Timeout')
    }
  })
  
  req.pipe(proxyReq)
}

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'serve-site',
      configureServer(server) {
        // Middleware: Reverse proxy для динамического контента (API, изображения, страницы)
        server.middlewares.use((req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/')
          const basePath = urlPath.split('?')[0]
          
          // Skip Vite/Vue internal paths
          if (basePath === '/' || basePath.startsWith('/@') || basePath.startsWith('/src/') ||
              basePath.startsWith('/node_modules/') || basePath.startsWith('/__')) {
            return next()
          }
          
          // API cache: отдаём закешированные API ответы из api-cache/
          if (basePath.startsWith('/api/')) {
            const apiCacheDir = path.join(PROJECT_DIR, 'api-cache')
            if (fs.existsSync(apiCacheDir)) {
              const indexPath = path.join(apiCacheDir, '_index.json')
              if (fs.existsSync(indexPath)) {
                try {
                  const index = JSON.parse(fs.readFileSync(indexPath, 'utf-8'))
                  const apiPath = urlPath.startsWith('/') ? urlPath : '/' + urlPath
                  const cacheFile = index[apiPath]
                  if (cacheFile) {
                    const cached = JSON.parse(fs.readFileSync(path.join(apiCacheDir, cacheFile), 'utf-8'))
                    const body = typeof cached.body === 'string' ? cached.body : JSON.stringify(cached.body)
                    res.setHeader('Content-Type', cached.contentType || 'application/json')
                    res.setHeader('Access-Control-Allow-Origin', '*')
                    res.setHeader('Cache-Control', 'public, max-age=3600')
                    res.statusCode = cached.status || 200
                    res.end(body)
                    console.log(`[API Cache] ${apiPath}`)
                    return
                  }
                } catch (e) {
                  console.log(`[API Cache Error] ${e.message}`)
                }
              }
            }
            // Fallback: проксируем к origin если нет в кеше
            if (mainDomain) {
              proxyToOrigin(mainDomain, req, res)
              return
            }
          }
          
          // /public/ и /unpublished/ пути: проксируем (нет локальных файлов)
          if (mainDomain && (basePath.startsWith('/public/') || basePath.startsWith('/unpublished/'))) {
            proxyToOrigin(mainDomain, req, res)
            return
          }
          
          // _next/ пути: проксируем если файл не найден локально (недоскачанные чанки, изображения, данные)
          if (mainDomain && basePath.startsWith('/_next/')) {
            const localFile = findFile(basePath)
            if (!localFile) {
              proxyToOrigin(mainDomain, req, res)
              return
            }
          }
          
          next()
        })
        
        // Middleware: Block Shopify tracking/analytics endpoints (return empty JS)
        server.middlewares.use((req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]
          
          if (urlPath.includes('shopifycloud/') || 
              urlPath.includes('checkouts/internal/') ||
              urlPath.includes('privacy-banner/') ||
              urlPath.includes('shop-js/') ||
              urlPath.includes('web-pixels') ||
              urlPath.includes('perf-kit/') ||
              urlPath.includes('trekkie') ||
              urlPath.includes('monorail')) {
            res.setHeader('Content-Type', 'application/javascript')
            res.setHeader('Access-Control-Allow-Origin', '*')
            res.statusCode = 200
            return res.end('// Shopify stub')
          }
          next()
        })
        
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

          // For HTML page paths (no ext or .html): redirect to Vue wrapper
          if (!ext || ext === '.html') {
            const filePath = findFile(urlPath)
            if (filePath && filePath.endsWith('.html')) {
              if (isFromIframe) {
                // Request from iframe - serve file directly (internal navigation)
                serveFile(filePath, res)
                return
              } else {
                // Top-level navigation - redirect to Vue wrapper
                const pagePath = urlPath.replace(/^\//, '')
                res.writeHead(302, { Location: '/?page=' + encodeURIComponent(pagePath) })
                res.end()
                return
              }
            } else if (isFromIframe) {
              // Из iframe — навигация ушла из /__raw контекста
              // Перенаправляем обратно через parent postMessage
              const pagePath = urlPath.replace(/^\//, '')
              const escaped = pagePath.replace(/'/g, "\\'").replace(/</g, '&lt;')
              res.setHeader('Content-Type', 'text/html; charset=utf-8')
              res.statusCode = 200
              res.end(`<!DOCTYPE html><html><body><script>var p='${escaped}';if(parent!==window){parent.postMessage({type:'WCLONER_NAVIGATION',path:p},'*')}else{location.replace('/?page='+encodeURIComponent(p))}</script></body></html>`)
              return
            } else if (!isFromIframe) {
              // Файл не найден локально — перенаправляем в Vue wrapper
              // __raw обработчик проксирует страницу с оригинального сервера
              const pagePath = urlPath.replace(/^\//, '')
              res.writeHead(302, { Location: '/?page=' + encodeURIComponent(pagePath) })
              res.end()
              return
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
          let urlPath = decodeURIComponent(req.url || '/')
          // Strip query params for path resolution but keep for file lookup
          const queryIndex = urlPath.indexOf('?')
          const basePath = queryIndex > -1 ? urlPath.substring(0, queryIndex) : urlPath

          // Default to index.html in main domain folder (учитываем вложенные пути)
          let resolvedPath = basePath
          if (basePath === '/' || basePath === '') {
            if (mainDomain && mainIndexPath) {
              resolvedPath = `/${mainDomain}/${mainIndexPath}`
            } else if (mainDomain) {
              resolvedPath = `/${mainDomain}/index.html`
            } else {
              resolvedPath = '/index.html'
            }
          }

          // If path starts with a domain folder, use it directly
          // e.g., /shop.eagles.com/cdn/... -> /shop.eagles.com/cdn/...
          let filePath = findFile(resolvedPath)
          
          // If not found and path doesn't start with domain, try prepending each domain
          // This handles relative paths like /cdn/shop/... from subdomain pages
          if (!filePath) {
            const startsWithDomain = domains.some(d => resolvedPath.startsWith('/' + d + '/'))
            if (!startsWithDomain) {
              for (const domain of domains) {
                const testPath = '/' + domain + resolvedPath
                filePath = findFile(testPath)
                if (filePath) break
              }
            }
          }
          
          if (filePath) {
            serveFile(filePath, res)
          } else if (mainDomain) {
            // Файл не найден — проксируем на оригинальный сервер (сохраняем /__raw контекст)
            proxyToOrigin(mainDomain, req, res, undefined, '/__raw')
          } else {
            res.statusCode = 404
            res.end('Not found: ' + basePath)
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
