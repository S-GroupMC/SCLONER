import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

// Find site content directory
function findSiteDir() {
  const siteDir = path.resolve(__dirname, '../_site')
  if (!fs.existsSync(siteDir)) return siteDir
  
  // Check for subdirectory with index.html
  const items = fs.readdirSync(siteDir)
  for (const item of items) {
    const itemPath = path.join(siteDir, item)
    if (fs.statSync(itemPath).isDirectory() && fs.existsSync(path.join(itemPath, 'index.html'))) {
      return itemPath
    }
  }
  return siteDir
}

const SITE_DIR = findSiteDir()

export default defineConfig({
  plugins: [
    vue(),
    // Serve static files from _site directory - no backend needed!
    {
      name: 'serve-site',
      configureServer(server) {
        server.middlewares.use('/__raw', (req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]
          let filePath = path.join(SITE_DIR, urlPath)
          
          // Default to index.html
          if (urlPath === '/' || urlPath === '') {
            filePath = path.join(SITE_DIR, 'index.html')
          } else if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
            filePath = path.join(filePath, 'index.html')
          }
          
          if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
            const ext = path.extname(filePath).toLowerCase()
            const mimeTypes = {
              '.html': 'text/html',
              '.css': 'text/css',
              '.js': 'application/javascript',
              '.json': 'application/json',
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.gif': 'image/gif',
              '.svg': 'image/svg+xml',
              '.webp': 'image/webp',
              '.woff2': 'font/woff2',
              '.woff': 'font/woff',
              '.ttf': 'font/ttf'
            }
            res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream')
            res.end(fs.readFileSync(filePath))
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
