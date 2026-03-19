"""
File Manager module - file operations, Vue wrapper generation, screenshots
"""
import os
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from .config import DOWNLOADS_DIR, PREVIEWS_DIR
from .utils import format_size, find_index_file


def download_missing_files(folder_path, base_url, missing_paths):
    """Download missing files from the original site."""
    import requests
    
    folder_path = Path(folder_path)
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    for file_path in missing_paths:
        parts = file_path.split('/')
        if len(parts) > 1 and '.' in parts[0]:
            url = f"https://{parts[0]}/{'/'.join(parts[1:])}"
        else:
            parsed = urlparse(base_url)
            url = f"{parsed.scheme}://{parsed.netloc}/{file_path}"
        
        local_file = folder_path / file_path
        
        try:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            
            if response.status_code == 200 and len(response.content) > 0:
                local_file.parent.mkdir(parents=True, exist_ok=True)
                with open(local_file, 'wb') as f:
                    f.write(response.content)
                
                results.append({
                    'path': file_path,
                    'status': 'downloaded',
                    'size': format_size(len(response.content)),
                    'url': url
                })
            else:
                results.append({
                    'path': file_path,
                    'status': 'failed',
                    'error': f'HTTP {response.status_code}',
                    'url': url
                })
        except Exception as e:
            results.append({
                'path': file_path,
                'status': 'error',
                'error': str(e),
                'url': url
            })
    
    downloaded = sum(1 for r in results if r['status'] == 'downloaded')
    failed = sum(1 for r in results if r['status'] != 'downloaded')
    
    return {
        'total': len(results),
        'downloaded': downloaded,
        'failed': failed,
        'results': results
    }


def generate_preview_screenshot(folder_path, main_domain, job_id, index_file=None):
    """Generate preview screenshot of the main page using Chrome headless"""
    folder_path = Path(folder_path)
    
    if not index_file:
        index_paths = [
            folder_path / 'index.html',
            folder_path / main_domain / 'index.html'
        ]
        
        for path in index_paths:
            if path.exists():
                index_file = path
                break
        
        if not index_file:
            index_file = find_index_file(folder_path)
    
    if not index_file:
        return None
    
    try:
        preview_path = folder_path / 'preview.png'
        
        chrome_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            shutil.which('chromium'),
            shutil.which('google-chrome')
        ]
        
        chrome_path = None
        for p in chrome_paths:
            if p and Path(p).exists():
                chrome_path = p
                break
        
        if chrome_path:
            local_file_url = f'file://{index_file.absolute()}'
            
            result = subprocess.run([
                chrome_path,
                '--headless=new',
                '--disable-gpu',
                '--no-sandbox',
                '--disable-web-security',
                '--allow-file-access-from-files',
                f'--screenshot={preview_path}',
                '--window-size=1280,800',
                '--hide-scrollbars',
                local_file_url
            ], capture_output=True, text=True, timeout=30)
            
            if preview_path.exists() and preview_path.stat().st_size > 100:
                return preview_path
        
        # Fallback: create placeholder
        placeholder_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        preview_path.write_bytes(placeholder_png)
        return preview_path
            
    except Exception as e:
        return None


def generate_vue_wrapper(folder_path, main_domain, port=3000, backend_port=3001):
    """Generate Vue wrapper with iframe for a downloaded site"""
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return False
    
    template_dir = Path(__file__).parent.parent / 'templates' / 'vue_wrapper'
    if not template_dir.exists():
        return False
    
    try:
        vue_dir = folder_path / 'vue-app'
        vue_dir.mkdir(exist_ok=True)
        
        src_dir = vue_dir / 'src'
        src_dir.mkdir(exist_ok=True)
        
        package_name = main_domain.replace('.', '-')
        
        # index.html
        with open(template_dir / 'index.html', 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('{{MAIN_DOMAIN}}', main_domain)
        with open(vue_dir / 'index.html', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # App.vue
        shutil.copy(template_dir / 'App.vue', src_dir / 'App.vue')
        
        # main.js
        shutil.copy(template_dir / 'main.js', src_dir / 'main.js')
        
        # package.json
        with open(template_dir / 'package.json', 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('{{PACKAGE_NAME}}', package_name)
        content = content.replace('{{MAIN_DOMAIN}}', main_domain)
        with open(vue_dir / 'package.json', 'w', encoding='utf-8') as f:
            f.write(content)
        
        # vite.config.js
        shutil.copy(template_dir / 'vite.config.js', vue_dir / 'vite.config.js')
        
        # Backend server.js
        shutil.copy(template_dir / 'server.js', folder_path / 'backend-server.js')
        os.chmod(folder_path / 'backend-server.js', 0o755)
        
        # README
        readme_content = f"""# {main_domain} - Vue Wrapper

## Быстрый старт

### 1. Установка
```bash
cd vue-app
npm install
```

### 2. Запуск (два терминала)

**Терминал 1** - Backend:
```bash
node backend-server.js
```

**Терминал 2** - Vue:
```bash
cd vue-app
npm run dev
```

Откройте: http://localhost:{port}

---
Создано WCLoner
"""
        
        with open(folder_path / 'README-VUE.md', 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        return True
        
    except Exception as e:
        return False


def generate_server_files(folder_path, main_domain, port=3000, with_vue=False):
    """Generate server files for a downloaded site"""
    if with_vue:
        return generate_vue_wrapper(folder_path, main_domain, port, port + 1)
    
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return False
    
    template_dir = Path(__file__).parent.parent / 'templates'
    server_template_path = template_dir / 'server_template.js'
    
    if not server_template_path.exists():
        return False
    
    try:
        with open(server_template_path, 'r', encoding='utf-8') as f:
            server_content = f.read()
        
        server_content = server_content.replace('{{PORT}}', str(port))
        server_content = server_content.replace('{{MAIN_DOMAIN}}', main_domain)
        
        with open(folder_path / 'server.js', 'w', encoding='utf-8') as f:
            f.write(server_content)
        
        os.chmod(folder_path / 'server.js', 0o755)
        
        return True
        
    except Exception as e:
        return False


def prepare_landing_folder(url, folder_name=None):
    """Create landing folder and copy templates WITHOUT downloading"""
    from datetime import datetime
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    
    if not folder_name:
        folder_name = domain
    
    folder_path = DOWNLOADS_DIR / folder_name
    
    if folder_path.exists():
        # Return existing folder info
        meta_path = folder_path / '_wcloner' / 'landing.json'
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            return {
                'folder_name': folder_name,
                'folder_path': str(folder_path),
                'url': url,
                'domain': domain,
                'status': meta.get('status', 'exists'),
                'existing': True,
                'landing_meta': meta
            }
    
    # Create new folder
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create _wcloner metadata folder
    wcloner_dir = folder_path / '_wcloner'
    wcloner_dir.mkdir(exist_ok=True)
    
    # Create landing metadata
    landing_meta = {
        'url': url,
        'domain': domain,
        'folder_name': folder_name,
        'created_at': datetime.now().isoformat(),
        'status': 'prepared',
        'scan_result': None,
        'selected_domains': [],
        'download_job_id': None
    }
    
    with open(wcloner_dir / 'landing.json', 'w') as f:
        json.dump(landing_meta, f, indent=2)
    
    # Copy Vue wrapper templates
    template_dir = Path(__file__).parent.parent / 'templates' / 'vue_wrapper'
    if template_dir.exists():
        vue_dir = folder_path / 'vue-app'
        vue_dir.mkdir(exist_ok=True)
        
        src_dir = vue_dir / 'src'
        src_dir.mkdir(exist_ok=True)
        
        package_name = domain.replace('.', '-')
        
        # Copy and customize templates
        if (template_dir / 'index.html').exists():
            with open(template_dir / 'index.html', 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('{{MAIN_DOMAIN}}', domain)
            with open(vue_dir / 'index.html', 'w', encoding='utf-8') as f:
                f.write(content)
        
        if (template_dir / 'App.vue').exists():
            shutil.copy(template_dir / 'App.vue', src_dir / 'App.vue')
        
        if (template_dir / 'main.js').exists():
            shutil.copy(template_dir / 'main.js', src_dir / 'main.js')
        
        if (template_dir / 'package.json').exists():
            with open(template_dir / 'package.json', 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace('{{PACKAGE_NAME}}', package_name)
            with open(vue_dir / 'package.json', 'w', encoding='utf-8') as f:
                f.write(content)
        
        if (template_dir / 'vite.config.js').exists():
            shutil.copy(template_dir / 'vite.config.js', vue_dir / 'vite.config.js')
        
        if (template_dir / 'server.js').exists():
            shutil.copy(template_dir / 'server.js', folder_path / 'backend-server.js')
            os.chmod(folder_path / 'backend-server.js', 0o755)
    
    return {
        'folder_name': folder_name,
        'folder_path': str(folder_path),
        'url': url,
        'domain': domain,
        'status': 'prepared',
        'existing': False,
        'landing_meta': landing_meta
    }


def get_folder_stats(folder_path):
    """Get statistics for a folder"""
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return None
    
    stats = {
        'total_files': 0,
        'total_size': 0,
        'html_files': 0,
        'css_files': 0,
        'js_files': 0,
        'image_files': 0
    }
    
    for f in folder_path.rglob('*'):
        if f.is_file() and '_wcloner' not in str(f) and 'vue-app' not in str(f) and 'node_modules' not in str(f):
            stats['total_files'] += 1
            stats['total_size'] += f.stat().st_size
            
            ext = f.suffix.lower()
            if ext in ['.html', '.htm']:
                stats['html_files'] += 1
            elif ext == '.css':
                stats['css_files'] += 1
            elif ext == '.js':
                stats['js_files'] += 1
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico']:
                stats['image_files'] += 1
    
    stats['total_size_formatted'] = format_size(stats['total_size'])
    
    return stats
