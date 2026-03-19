"""
Server Manager module - start/stop Vue and backend servers
"""
import os
import subprocess
import socket
from pathlib import Path

from .config import DOWNLOADS_DIR, running_servers


def get_domain_ports(folder_name):
    """Get or assign ports for a domain"""
    ports_file = DOWNLOADS_DIR / folder_name / '_wcloner' / 'ports.json'
    
    if ports_file.exists():
        import json
        with open(ports_file, 'r') as f:
            return json.load(f)
    
    # Find free ports
    vue_port = find_free_port(3000)
    backend_port = find_free_port(vue_port + 1)
    
    ports = {
        'vue_port': vue_port,
        'backend_port': backend_port
    }
    
    # Save ports
    ports_file.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(ports_file, 'w') as f:
        json.dump(ports, f)
    
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
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


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
    """Start Vue dev server for a downloaded site"""
    folder_path = DOWNLOADS_DIR / folder_name
    vue_dir = folder_path / 'vue-app'
    
    if not vue_dir.exists():
        return {'error': 'Vue app not found. Generate scripts first.'}
    
    # Check if package.json exists
    if not (vue_dir / 'package.json').exists():
        return {'error': 'package.json not found in vue-app'}
    
    # Get ports
    ports = get_domain_ports(folder_name)
    vue_port = ports['vue_port']
    backend_port = ports['backend_port']
    
    # Check if already running
    if folder_name in running_servers:
        servers = running_servers[folder_name]
        if 'vue' in servers and check_process_running(servers['vue'].get('pid', 0)):
            return {
                'status': 'already_running',
                'vue_port': servers['vue']['port'],
                'backend_port': servers.get('backend', {}).get('port'),
                'url': f"http://localhost:{servers['vue']['port']}"
            }
    
    # Install dependencies if needed
    if not (vue_dir / 'node_modules').exists():
        install_process = subprocess.run(
            ['npm', 'install'],
            cwd=str(vue_dir),
            capture_output=True,
            text=True,
            timeout=120
        )
        if install_process.returncode != 0:
            return {'error': f'npm install failed: {install_process.stderr}'}
    
    # Start backend server first
    backend_server_path = folder_path / 'backend-server.js'
    if backend_server_path.exists():
        env = os.environ.copy()
        env['PORT'] = str(backend_port)
        
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
    
    # Start Vue dev server
    env = os.environ.copy()
    env['VITE_BACKEND_PORT'] = str(backend_port)
    
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
    
    return {
        'status': 'started',
        'vue_port': vue_port,
        'backend_port': backend_port,
        'url': f"http://localhost:{vue_port}",
        'vue_pid': vue_process.pid,
        'backend_pid': running_servers[folder_name].get('backend', {}).get('pid')
    }


def start_backend_server(folder_name):
    """Start backend Node.js server for a downloaded site"""
    folder_path = DOWNLOADS_DIR / folder_name
    
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
    
    return {'status': 'stopped', 'server': 'vue'}


def stop_all_servers():
    """Stop all running servers"""
    all_folders = list(running_servers.keys())
    results = {}
    
    for folder_name in all_folders:
        results[folder_name] = stop_servers(folder_name)
    
    return results
