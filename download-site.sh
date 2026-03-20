#!/bin/bash
# Download site with wget for Vue wrapper
# Usage: ./download-site.sh <url> [output_dir]

set -e

URL="${1:-https://eagles.com}"
OUTPUT_DIR="${2:-downloads}"
DOMAIN=$(echo "$URL" | sed -E 's|https?://([^/]+).*|\1|')

echo "=== Downloading $URL ==="
echo "Output: $OUTPUT_DIR/$DOMAIN"

mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# Download with wget
wget2 \
  --mirror \
  --convert-links \
  --adjust-extension \
  --page-requisites \
  --no-parent \
  --execute robots=off \
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  --wait=0.5 \
  --random-wait \
  --no-check-certificate \
  --restrict-file-names=windows \
  --directory-prefix="$DOMAIN" \
  "$URL" 2>&1 || true

echo ""
echo "=== Post-processing ==="

# Find site directory
SITE_DIR="$DOMAIN/$DOMAIN"
if [ ! -d "$SITE_DIR" ]; then
  SITE_DIR="$DOMAIN"
fi

echo "Site directory: $SITE_DIR"

# 1. Fix media="print" to media="all"
echo "Fixing media='print' attributes..."
find "$SITE_DIR" -name "*.html" -exec sed -i '' 's/media="print" onload="this\.media='"'"'all'"'"'"/media="all"/g' {} \; 2>/dev/null || true

# 2. Download CSS variables from original site
echo "Downloading CSS variables from $URL..."
ASSETS_DIR="$SITE_DIR/cdn/shop/t/3/assets"
mkdir -p "$ASSETS_DIR"

# Extract :root variables
curl -sL "$URL" 2>/dev/null | sed -n '/:root {/,/^      }/p' > "$ASSETS_DIR/theme-variables.css"

# Add additional CSS
cat >> "$ASSETS_DIR/theme-variables.css" << 'CSSEOF'

/* Color scheme variables */
:root {
  --color-foreground: 255, 255, 255;
  --color-background: 0, 0, 0;
  --gradient-background: #000000;
  --color-button: 255, 255, 255;
  --color-button-text: 0, 0, 0;
  --color-secondary-button: 0, 0, 0;
  --color-secondary-button-text: 255, 255, 255;
  --color-link: 255, 255, 255;
  --color-badge-foreground: 255, 255, 255;
  --color-badge-background: 0, 0, 0;
  --color-badge-border: 255, 255, 255;
  --alpha-badge-border: 0.1;
  --alpha-button-background: 1;
  --alpha-link: 0.85;
  --duration-short: 100ms;
  --duration-default: 200ms;
  --duration-long: 500ms;
}

*, *::before, *::after { box-sizing: border-box; }
html { font-size: calc(var(--font-body-scale) * 62.5%); }
body {
  font-family: var(--font-body-family);
  font-style: var(--font-body-style);
  font-weight: var(--font-body-weight);
  color: rgb(var(--color-foreground));
  background-color: rgb(var(--color-background));
  margin: 0;
  font-size: 1.5rem;
  letter-spacing: 0.06rem;
  line-height: calc(1 + 0.8 / var(--font-body-scale));
}
CSSEOF

echo "Created $ASSETS_DIR/theme-variables.css"

# 3. Add theme-variables.css to all HTML files
echo "Adding theme-variables.css to HTML files..."
find "$SITE_DIR" -name "*.html" -exec sed -i '' 's|<head>|<head>\
<link rel="stylesheet" href="/cdn/shop/t/3/assets/theme-variables.css">|g' {} \; 2>/dev/null || true

# 4. Create simple Node.js server
cat > "$DOMAIN/server.js" << 'SERVEREOF'
const http = require('http')
const fs = require('fs')
const path = require('path')

const PORT = process.env.PORT || 3000
const SITE_DIR = path.join(__dirname, path.basename(__dirname))

const mimeTypes = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml',
  '.webp': 'image/webp', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.ttf': 'font/ttf', '.ico': 'image/x-icon'
}

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0])
  
  if (urlPath.includes('/.well-known/') || urlPath.includes('/monorail/')) {
    res.writeHead(200, { 'Content-Type': 'application/json' })
    return res.end('{}')
  }
  
  if (urlPath === '/') urlPath = '/index.html'
  
  let filePath = path.join(SITE_DIR, urlPath)
  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html')
  }
  if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    if (fs.existsSync(filePath + '.html')) filePath += '.html'
  }
  
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase()
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' })
    fs.createReadStream(filePath).pipe(res)
  } else {
    res.writeHead(404)
    res.end('Not found: ' + urlPath)
  }
})

server.listen(PORT, () => console.log(`Server: http://localhost:${PORT}/`))
SERVEREOF

echo "Created $DOMAIN/server.js"

# Count files
HTML_COUNT=$(find "$SITE_DIR" -name "*.html" | wc -l | tr -d ' ')
CSS_COUNT=$(find "$SITE_DIR" -name "*.css" | wc -l | tr -d ' ')
JS_COUNT=$(find "$SITE_DIR" -name "*.js" | wc -l | tr -d ' ')

echo ""
echo "=== Done ==="
echo "HTML files: $HTML_COUNT"
echo "CSS files: $CSS_COUNT"
echo "JS files: $JS_COUNT"
echo ""
echo "To run: cd $OUTPUT_DIR/$DOMAIN && node server.js"
