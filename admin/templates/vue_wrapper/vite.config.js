import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

// Directories to exclude from serving
const EXCLUDE_DIRS = ['vue-app', 'node_modules', '_wcloner', '.git', '_site']

// Site content is in project root (wget creates domain folders like eagles.com/, shop.eagles.com/)
const PROJECT_DIR = path.resolve(__dirname, '..')

export default defineConfig({
  plugins: [
    vue(),
    // Serve static files from project directory
    {
      name: 'serve-site',
      configureServer(server) {
        server.middlewares.use('/__raw', (req, res, next) => {
          const urlPath = decodeURIComponent(req.url || '/').split('?')[0]
          let filePath = null
          
          // Find main domain folder
          let mainDomain = null
          const items = fs.readdirSync(PROJECT_DIR)
          for (const item of items) {
            if (EXCLUDE_DIRS.includes(item)) continue
            const itemPath = path.join(PROJECT_DIR, item)
            if (fs.statSync(itemPath).isDirectory() && fs.existsSync(path.join(itemPath, 'index.html'))) {
              mainDomain = item
              break
            }
          }
          
          // Default to index.html in main domain folder
          if (urlPath === '/' || urlPath === '') {
            if (mainDomain) {
              filePath = path.join(PROJECT_DIR, mainDomain, 'index.html')
            }
          } else {
            // Try direct path first
            let directPath = path.join(PROJECT_DIR, urlPath)
            if (fs.existsSync(directPath) && fs.statSync(directPath).isFile()) {
              filePath = directPath
            } else if (fs.existsSync(directPath) && fs.statSync(directPath).isDirectory()) {
              filePath = path.join(directPath, 'index.html')
            } else if (!fs.existsSync(directPath) && !path.extname(directPath) && fs.existsSync(directPath + '.html')) {
              filePath = directPath + '.html'
            }
            
            // If not found, try with main domain prefix
            if (!filePath && mainDomain) {
              const domainPath = path.join(PROJECT_DIR, mainDomain, urlPath)
              if (fs.existsSync(domainPath) && fs.statSync(domainPath).isFile()) {
                filePath = domainPath
              } else if (fs.existsSync(domainPath) && fs.statSync(domainPath).isDirectory()) {
                filePath = path.join(domainPath, 'index.html')
              } else if (!fs.existsSync(domainPath) && !path.extname(domainPath) && fs.existsSync(domainPath + '.html')) {
                filePath = domainPath + '.html'
              }
            }
          }
          
          if (filePath && fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
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
