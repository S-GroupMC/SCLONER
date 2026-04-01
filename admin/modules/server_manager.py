"""
Server Manager module - start/stop Vue and backend servers
"""
import json
import os
import shutil
import subprocess
import socket
import time
from pathlib import Path

from .config import DOWNLOADS_DIR, running_servers

TEMPLATE_DIR = Path(__file__).parent.parent / 'templates' / 'vue_wrapper'
SERVERS_REGISTRY = Path(__file__).parent.parent / '_wcloner_servers.json'


def _load_registry():
    """Load servers registry from JSON."""
    if SERVERS_REGISTRY.exists():
        try:
            return json.loads(SERVERS_REGISTRY.read_text())
        except Exception:
            pass
    return {}


def _save_registry(data):
    """Save servers registry to JSON."""
    try:
        SERVERS_REGISTRY.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[WCLoner] Failed to save registry: {e}")


def register_server(folder_name, server_type, pid, port):
    """Register a running server in the JSON registry."""
    reg = _load_registry()
    if folder_name not in reg:
        reg[folder_name] = {}
    reg[folder_name][server_type] = {
        'pid': pid,
        'port': port,
        'started': time.time()
    }
    _save_registry(reg)


def unregister_server(folder_name, server_type=None):
    """Remove a server from the registry."""
    reg = _load_registry()
    if folder_name in reg:
        if server_type:
            reg[folder_name].pop(server_type, None)
            if not reg[folder_name]:
                del reg[folder_name]
        else:
            del reg[folder_name]
        _save_registry(reg)


def kill_registered_servers():
    """Kill all servers from the registry. Called at startup to clean orphans."""
    import signal
    reg = _load_registry()
    if not reg:
        return 0
    
    killed = 0
    for folder_name, servers in reg.items():
        for srv_type, info in servers.items():
            pid = info.get('pid')
            port = info.get('port')
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                    killed += 1
                    print(f"[WCLoner] Killed {srv_type} PID {pid} (port {port}) for {folder_name}")
                except (ProcessLookupError, PermissionError):
                    pass
            if port:
                kill_port(port)
    
    # Clear registry
    _save_registry({})
    print(f"[WCLoner] Cleaned {killed} orphan server(s)")
    return killed


def kill_port(port):
    """Force kill any process listening on the given port. Returns True if killed."""
    import signal
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True, timeout=5
        )
        pids = result.stdout.strip()
        if not pids:
            return False
        for pid_str in pids.split('\n'):
            pid_str = pid_str.strip()
            if pid_str:
                try:
                    os.kill(int(pid_str), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        import time as _t
        _t.sleep(0.5)
        return True
    except Exception:
        return False


def _files_differ(file_a, file_b):
    """Compare two files by content. Returns True if different."""
    try:
        return file_a.read_bytes() != file_b.read_bytes()
    except Exception:
        return True


def sync_templates(folder_path):
    """Sync backend-server.js and vite.config.js from template if content differs."""
    synced = []
    
    # backend-server.js
    template_server = TEMPLATE_DIR / 'server.js'
    target_server = folder_path / 'backend-server.js'
    if template_server.exists():
        if not target_server.exists() or _files_differ(template_server, target_server):
            shutil.copy(template_server, target_server)
            synced.append('backend-server.js')
    
    # vite.config.js (reads mainDomain from _wcloner/landing.json at runtime)
    vue_dir = folder_path / 'vue-app'
    template_vite = TEMPLATE_DIR / 'vite.config.js'
    target_vite = vue_dir / 'vite.config.js'
    if template_vite.exists() and vue_dir.exists():
        if not target_vite.exists() or _files_differ(template_vite, target_vite):
            shutil.copy(template_vite, target_vite)
            synced.append('vite.config.js')
    
    if synced:
        print(f"[WCLoner] Synced templates: {', '.join(synced)}")
    
    return synced


BASE_PORT = 5600


def _get_all_assigned_ports():
    """Collect all ports already assigned to other sites from their ports.json files."""
    used = set()
    if not DOWNLOADS_DIR.exists():
        return used
    for folder in DOWNLOADS_DIR.iterdir():
        if not folder.is_dir():
            continue
        pf = folder / '_wcloner' / 'ports.json'
        if pf.exists():
            try:
                data = json.loads(pf.read_text())
                if data.get('vue_port'):
                    used.add(data['vue_port'])
                if data.get('backend_port'):
                    used.add(data['backend_port'])
            except Exception:
                pass
    return used


def get_domain_ports(folder_name):
    """Get or assign ports for a domain. Ports start from 5600, +1 for each new site."""
    ports_file = DOWNLOADS_DIR / folder_name / '_wcloner' / 'ports.json'
    
    if ports_file.exists():
        try:
            data = json.loads(ports_file.read_text())
            if data.get('vue_port') and data.get('backend_port'):
                return data
        except Exception:
            pass
    
    # Collect all ports already assigned to other sites
    assigned = _get_all_assigned_ports()
    
    # Find free ports starting from BASE_PORT, skipping assigned and in-use
    port = BASE_PORT
    vue_port = None
    backend_port = None
    
    while port < 65535:
        if port not in assigned and not is_port_in_use(port):
            if vue_port is None:
                vue_port = port
            elif backend_port is None:
                backend_port = port
                break
        port += 1
    
    if not vue_port or not backend_port:
        vue_port = vue_port or find_free_port(BASE_PORT)
        backend_port = backend_port or find_free_port(vue_port + 1)
    
    ports = {
        'vue_port': vue_port,
        'backend_port': backend_port
    }
    
    # Save ports
    ports_file.parent.mkdir(parents=True, exist_ok=True)
    ports_file.write_text(json.dumps(ports, indent=2))
    
    return ports


def find_free_port(start=3000):
    """Find a free port starting from the given number"""
    port = start
    while port < 65535:
        if not is_port_in_use(port):
            return port
        port += 1
    return start


def is_port_in_use(port):
    """Check if a port is in use (IPv4 + IPv6 + lsof fallback)"""
    # Check IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            return True
    # Check IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            if s.connect_ex(('::1', port)) == 0:
                return True
    except (OSError, socket.error):
        pass
    # lsof fallback (catches LISTEN state even if not accepting connections yet)
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True, timeout=3
        )
        if result.stdout.strip():
            return True
    except Exception:
        pass
    return False


def check_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_servers_status(folder_name):
    """Get status of running servers for a folder"""
    servers = running_servers.get(folder_name, {})
    
    status = {
        'vue_server': {
            'running': False,
            'pid': None,
            'port': None,
            'url': None
        },
        'backend_server': {
            'running': False,
            'pid': None,
            'port': None,
            'url': None
        }
    }
    
    if 'vue' in servers:
        vue = servers['vue']
        is_running = check_process_running(vue.get('pid', 0))
        status['vue_server'] = {
            'running': is_running,
            'pid': vue.get('pid'),
            'port': vue.get('port'),
            'url': f"http://localhost:{vue.get('port')}" if is_running else None
        }
    
    if 'backend' in servers:
        backend = servers['backend']
        is_running = check_process_running(backend.get('pid', 0))
        status['backend_server'] = {
            'running': is_running,
            'pid': backend.get('pid'),
            'port': backend.get('port'),
            'url': f"http://localhost:{backend.get('port')}" if is_running else None
        }
    
    return status


def start_vue_server(folder_name):
    """Start Vue dev server for a downloaded site. Returns detailed steps log."""
    import time
    
    folder_path = DOWNLOADS_DIR / folder_name
    vue_dir = folder_path / 'vue-app'
    steps = []
    
    def step(name, status, detail=''):
        steps.append({'name': name, 'status': status, 'detail': detail})
    
    # Step 1: Check vue-app exists
    if not vue_dir.exists():
        step('vue-app', 'error', 'Vue app not found. Generate scripts first.')
        return {'error': 'Vue app not found', 'steps': steps}
    step('vue-app', 'ok', str(vue_dir))
    
    # Step 2: Check package.json
    if not (vue_dir / 'package.json').exists():
        step('package.json', 'error', 'Not found in vue-app')
        return {'error': 'package.json not found', 'steps': steps}
    step('package.json', 'ok')
    
    # Step 3: Check backend-server.js
    backend_server_path = folder_path / 'backend-server.js'
    if backend_server_path.exists():
        step('backend-server.js', 'ok')
    else:
        step('backend-server.js', 'warn', 'Not found, backend will not start')
    
    # Step 4: Get ports
    ports = get_domain_ports(folder_name)
    vue_port = ports['vue_port']
    backend_port = ports['backend_port']
    step('ports', 'ok', f'Vue: {vue_port}, Backend: {backend_port}')
    
    # Step 5: Check if already running
    if folder_name in running_servers:
        servers = running_servers[folder_name]
        if 'vue' in servers and check_process_running(servers['vue'].get('pid', 0)):
            step('already_running', 'ok', f"PID {servers['vue'].get('pid')}, port {servers['vue']['port']}")
            return {
                'status': 'already_running',
                'vue_port': servers['vue']['port'],
                'backend_port': servers.get('backend', {}).get('port'),
                'url': f"http://localhost:{servers['vue']['port']}",
                'steps': steps
            }
    
    # Step 6: Sync templates
    synced = sync_templates(folder_path)
    if synced:
        step('sync_templates', 'ok', f'Updated: {", ".join(synced)}')
    else:
        step('sync_templates', 'ok', 'Templates up to date')
    
    # Step 7: npm install if needed
    if not (vue_dir / 'node_modules').exists():
        step('npm_install', 'running', 'Installing dependencies...')
        try:
            t0 = time.time()
            install_process = subprocess.run(
                ['npm', 'install'],
                cwd=str(vue_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            elapsed = round(time.time() - t0, 1)
            if install_process.returncode != 0:
                steps[-1] = {'name': 'npm_install', 'status': 'error', 'detail': install_process.stderr[:300]}
                return {'error': 'npm install failed', 'steps': steps}
            steps[-1] = {'name': 'npm_install', 'status': 'ok', 'detail': f'Installed in {elapsed}s'}
        except subprocess.TimeoutExpired:
            steps[-1] = {'name': 'npm_install', 'status': 'error', 'detail': 'Timeout after 120s'}
            return {'error': 'npm install timeout', 'steps': steps}
    else:
        step('npm_install', 'ok', 'node_modules exists')
    
    # Step 8: Start backend server
    if backend_server_path.exists():
        # Check if port is occupied by another site's server
        if is_port_in_use(backend_port):
            step('port_conflict', 'warn', f'Port {backend_port} occupied, skipping kill to protect other servers')
        step('port_check', 'ok', f'Backend port {backend_port}')
        
        env = os.environ.copy()
        env['PORT'] = str(backend_port)
        
        try:
            backend_process = subprocess.Popen(
                ['node', str(backend_server_path)],
                cwd=str(folder_path),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if folder_name not in running_servers:
                running_servers[folder_name] = {}
            
            running_servers[folder_name]['backend'] = {
                'pid': backend_process.pid,
                'port': backend_port,
                'process': backend_process
            }
            register_server(folder_name, 'backend', backend_process.pid, backend_port)
            
            # Wait and check if process crashed immediately
            time.sleep(1.0)
            exit_code = backend_process.poll()
            if exit_code is not None:
                stdout = backend_process.stdout.read().decode('utf-8', errors='replace')[:300]
                stderr = backend_process.stderr.read().decode('utf-8', errors='replace')[:300]
                detail = stderr or stdout or f'exit code {exit_code}'
                step('backend_start', 'error', f'Crashed: {detail}')
                return {'error': 'Backend server crashed', 'steps': steps}
            
            # Verify port is actually listening
            if not is_port_in_use(backend_port):
                time.sleep(1.0)
                if not is_port_in_use(backend_port):
                    step('backend_start', 'warn', f'PID {backend_process.pid} running, but port {backend_port} not yet open')
                else:
                    step('backend_start', 'ok', f'PID {backend_process.pid}, port {backend_port}')
            else:
                step('backend_start', 'ok', f'PID {backend_process.pid}, port {backend_port}')
        except Exception as e:
            step('backend_start', 'error', str(e)[:200])
            return {'error': f'Backend start failed: {e}', 'steps': steps}
    else:
        step('backend_start', 'skip', 'No backend-server.js')
    
    # Step 9: Start Vue dev server
    # Check port availability (don't kill - may belong to another site)
    if is_port_in_use(vue_port):
        step('port_conflict_vue', 'warn', f'Port {vue_port} already in use')
    step('port_check_vue', 'ok', f'Vue port {vue_port}')
    
    env = os.environ.copy()
    env['VITE_BACKEND_PORT'] = str(backend_port)
    
    try:
        vue_process = subprocess.Popen(
            ['npm', 'run', 'dev', '--', '--port', str(vue_port)],
            cwd=str(vue_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if folder_name not in running_servers:
            running_servers[folder_name] = {}
        
        running_servers[folder_name]['vue'] = {
            'pid': vue_process.pid,
            'port': vue_port,
            'process': vue_process
        }
        register_server(folder_name, 'vue', vue_process.pid, vue_port)
        
        # Brief wait to check if process crashed immediately
        time.sleep(0.5)
        if vue_process.poll() is not None:
            stderr = vue_process.stderr.read().decode('utf-8', errors='replace')[:300]
            step('vue_start', 'error', f'Crashed: {stderr}')
            return {'error': 'Vue server crashed', 'steps': steps}
        
        step('vue_start', 'ok', f'PID {vue_process.pid}, port {vue_port}')
    except Exception as e:
        step('vue_start', 'error', str(e)[:200])
        return {'error': f'Vue start failed: {e}', 'steps': steps}
    
    # Step 10: Verify port is accessible (give Vite time to start)
    for attempt in range(10):
        time.sleep(1)
        if is_port_in_use(vue_port):
            step('verify', 'ok', f'http://localhost:{vue_port} responding ({attempt+1}s)')
            break
    else:
        step('verify', 'warn', f'Port {vue_port} not responding after 10s')
    
    return {
        'status': 'started',
        'vue_port': vue_port,
        'backend_port': backend_port,
        'url': f"http://localhost:{vue_port}",
        'vue_pid': vue_process.pid,
        'backend_pid': running_servers[folder_name].get('backend', {}).get('pid'),
        'steps': steps
    }


def start_backend_server(folder_name):
    """Start backend Node.js server for a downloaded site"""
    folder_path = DOWNLOADS_DIR / folder_name
    
    # Sync templates before starting
    sync_templates(folder_path)
    
    backend_server_path = folder_path / 'backend-server.js'
    if not backend_server_path.exists():
        backend_server_path = folder_path / 'server.js'
    
    if not backend_server_path.exists():
        return {'error': 'Server script not found'}
    
    ports = get_domain_ports(folder_name)
    backend_port = ports['backend_port']
    
    # Check if already running
    if folder_name in running_servers:
        servers = running_servers[folder_name]
        if 'backend' in servers and check_process_running(servers['backend'].get('pid', 0)):
            return {
                'status': 'already_running',
                'port': servers['backend']['port'],
                'url': f"http://localhost:{servers['backend']['port']}"
            }
    
    env = os.environ.copy()
    env['PORT'] = str(backend_port)
    
    process = subprocess.Popen(
        ['node', str(backend_server_path)],
        cwd=str(folder_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    if folder_name not in running_servers:
        running_servers[folder_name] = {}
    
    running_servers[folder_name]['backend'] = {
        'pid': process.pid,
        'port': backend_port,
        'process': process
    }
    register_server(folder_name, 'backend', process.pid, backend_port)
    
    return {
        'status': 'started',
        'port': backend_port,
        'url': f"http://localhost:{backend_port}",
        'pid': process.pid
    }


def stop_servers(folder_name):
    """Stop all running servers for a folder"""
    servers = running_servers.get(folder_name, {})
    
    stopped = []
    
    for server_type, server_info in servers.items():
        pid = server_info.get('pid')
        if pid:
            try:
                os.kill(pid, 9)
                stopped.append(server_type)
            except (OSError, ProcessLookupError):
                pass
    
    if folder_name in running_servers:
        del running_servers[folder_name]
    unregister_server(folder_name)
    
    return {
        'status': 'stopped',
        'stopped_servers': stopped
    }


def stop_vue_server(folder_name):
    """Stop only Vue server for a folder"""
    servers = running_servers.get(folder_name, {})
    vue_info = servers.get('vue')
    
    if not vue_info:
        return {'status': 'not_running'}
    
    pid = vue_info.get('pid')
    if pid:
        try:
            os.kill(pid, 9)
        except (OSError, ProcessLookupError):
            pass
    
    if folder_name in running_servers and 'vue' in running_servers[folder_name]:
        del running_servers[folder_name]['vue']
    unregister_server(folder_name, 'vue')
    
    return {'status': 'stopped', 'server': 'vue'}


def restart_vue_only(folder_name):
    """Restart only Vue (Vite) server, do NOT touch backend Node.js server"""
    import time
    
    folder_path = DOWNLOADS_DIR / folder_name
    vue_dir = folder_path / 'vue-app'
    
    if not vue_dir.exists():
        return {'error': 'Vue app not found'}
    
    # Get ports
    ports = get_domain_ports(folder_name)
    vue_port = ports['vue_port']
    backend_port = ports['backend_port']
    
    # Stop only Vue process
    servers = running_servers.get(folder_name, {})
    vue_info = servers.get('vue')
    if vue_info:
        pid = vue_info.get('pid')
        if pid:
            try:
                os.kill(pid, 9)
            except (OSError, ProcessLookupError):
                pass
        if folder_name in running_servers and 'vue' in running_servers[folder_name]:
            del running_servers[folder_name]['vue']
        unregister_server(folder_name, 'vue')
    
    # Kill port just in case
    kill_port(vue_port)
    time.sleep(0.5)
    
    # Sync templates before restart
    sync_templates(folder_path)
    
    # Start Vue only
    env = os.environ.copy()
    env['VITE_BACKEND_PORT'] = str(backend_port)
    
    try:
        vue_process = subprocess.Popen(
            ['npm', 'run', 'dev', '--', '--port', str(vue_port)],
            cwd=str(vue_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if folder_name not in running_servers:
            running_servers[folder_name] = {}
        
        running_servers[folder_name]['vue'] = {
            'pid': vue_process.pid,
            'port': vue_port,
            'process': vue_process
        }
        register_server(folder_name, 'vue', vue_process.pid, vue_port)
        
        # Wait for Vite to start
        for attempt in range(10):
            time.sleep(1)
            if is_port_in_use(vue_port):
                break
        
        return {
            'status': 'restarted',
            'vue_port': vue_port,
            'vue_pid': vue_process.pid,
            'url': f'http://localhost:{vue_port}'
        }
    except Exception as e:
        return {'error': f'Vue restart failed: {e}'}


def stop_all_servers():
    """Stop all running servers"""
    all_folders = list(running_servers.keys())
    results = {}
    
    for folder_name in all_folders:
        results[folder_name] = stop_servers(folder_name)
    
    # Also kill any orphans from registry
    kill_registered_servers()
    
    return results
