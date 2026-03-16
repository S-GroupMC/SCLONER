import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: {{PORT}},
    proxy: {
      // Proxy /__raw/* to Node.js server serving static files
      '/__raw': {
        target: 'http://localhost:{{BACKEND_PORT}}',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  }
})
