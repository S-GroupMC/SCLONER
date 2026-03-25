"""
Link Fixer - модуль исправления битых ссылок
Анализирует битые ссылки и исправляет их если ресурс доступен локально
"""
import os
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin

from .config import DOWNLOADS_DIR


def find_local_file(folder_path, broken_link, referenced_from):
    """
    Ищет локальный файл который может соответствовать битой ссылке.
    Возвращает путь к найденному файлу или None.
    """
    folder_path = Path(folder_path)
    
    # Убираем query string и якоря
    clean_link = broken_link.split('?')[0].split('#')[0]
    
    # Получаем имя файла
    filename = os.path.basename(clean_link)
    if not filename:
        filename = 'index.html'
    
    # Варианты поиска
    search_variants = []
    
    # 1. Прямой путь от корня
    if clean_link.startswith('/'):
        search_variants.append(folder_path / clean_link.lstrip('/'))
    
    # 2. Относительный путь от файла где ссылка
    ref_dir = (folder_path / referenced_from).parent
    search_variants.append(ref_dir / clean_link)
    
    # 3. Поиск по имени файла в разных папках
    for domain_folder in folder_path.iterdir():
        if domain_folder.is_dir() and not domain_folder.name.startswith(('_', '.')):
            # Ищем файл с таким именем
            for found in domain_folder.rglob(filename):
                if found.is_file():
                    search_variants.append(found)
    
    # 4. Проверяем варианты
    for variant in search_variants:
        if variant.exists() and variant.is_file():
            try:
                rel_path = variant.relative_to(folder_path)
                return {
                    'found': True,
                    'local_path': str(rel_path),
                    'absolute_path': str(variant),
                    'fix_type': 'local'
                }
            except ValueError:
                continue
        
        # Проверяем с index.html для директорий
        if variant.is_dir() and (variant / 'index.html').exists():
            try:
                rel_path = (variant / 'index.html').relative_to(folder_path)
                return {
                    'found': True,
                    'local_path': str(rel_path.parent) + '/',
                    'absolute_path': str(variant / 'index.html'),
                    'fix_type': 'local'
                }
            except ValueError:
                continue
    
    return {'found': False, 'fix_type': 'download_needed'}


def analyze_broken_links(folder_path, broken_links):
    """
    Анализирует битые ссылки и определяет как их можно исправить.
    
    Возвращает:
    - fixable_local: ссылки которые можно исправить (файл есть локально)
    - need_download: ссылки которые требуют скачивания
    - unfixable: ссылки которые нельзя исправить
    """
    folder_path = Path(folder_path)
    
    fixable_local = []
    need_download = []
    unfixable = []
    
    for bl in broken_links:
        link = bl.get('link', '')
        referenced_from = bl.get('referenced_from', '')
        link_type = bl.get('type', 'other')
        
        # Пропускаем внешние ссылки
        if link.startswith(('http://', 'https://', '//')):
            unfixable.append({
                **bl,
                'reason': 'external_link',
                'description': 'Внешняя ссылка - требует ручной проверки'
            })
            continue
        
        # Ищем локальный файл
        result = find_local_file(folder_path, link, referenced_from)
        
        if result['found']:
            fixable_local.append({
                **bl,
                'fix': result,
                'new_path': result['local_path'],
                'description': f'Файл найден: {result["local_path"]}'
            })
        else:
            # Определяем можно ли скачать
            if link_type in ('page', 'script', 'style', 'image', 'font'):
                need_download.append({
                    **bl,
                    'description': f'Файл не найден локально, можно скачать'
                })
            else:
                unfixable.append({
                    **bl,
                    'reason': 'not_found',
                    'description': 'Файл не найден и не может быть скачан'
                })
    
    return {
        'fixable_local': fixable_local,
        'need_download': need_download,
        'unfixable': unfixable,
        'summary': {
            'total': len(broken_links),
            'can_fix_now': len(fixable_local),
            'need_download': len(need_download),
            'unfixable': len(unfixable)
        }
    }


def fix_link_in_file(file_path, old_link, new_link):
    """
    Заменяет ссылку в файле.
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return {'success': False, 'error': 'File not found'}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Экранируем специальные символы для regex
        old_escaped = re.escape(old_link)
        
        # Паттерны для замены (href="..." и src="...")
        patterns = [
            (rf'(href=["\'])({old_escaped})(["\'])', rf'\g<1>{new_link}\g<3>'),
            (rf'(src=["\'])({old_escaped})(["\'])', rf'\g<1>{new_link}\g<3>'),
        ]
        
        replaced = False
        for pattern, replacement in patterns:
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                replaced = True
        
        if replaced:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {'success': True, 'replaced': True}
        else:
            return {'success': True, 'replaced': False, 'message': 'Link not found in file'}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fix_broken_links(folder_path, links_to_fix):
    """
    Исправляет список битых ссылок.
    
    links_to_fix: список объектов с полями:
        - link: оригинальная битая ссылка
        - new_path: новый путь
        - referenced_from: файл где ссылка
    """
    folder_path = Path(folder_path)
    
    fixed = []
    failed = []
    
    for item in links_to_fix:
        old_link = item.get('link')
        new_link = item.get('new_path')
        ref_file = item.get('referenced_from')
        
        if not all([old_link, new_link, ref_file]):
            failed.append({
                **item,
                'error': 'Missing required fields'
            })
            continue
        
        file_path = folder_path / ref_file
        result = fix_link_in_file(file_path, old_link, new_link)
        
        if result.get('success') and result.get('replaced'):
            fixed.append({
                **item,
                'status': 'fixed'
            })
        else:
            failed.append({
                **item,
                'error': result.get('error') or result.get('message', 'Unknown error')
            })
    
    return {
        'fixed': fixed,
        'failed': failed,
        'summary': {
            'total': len(links_to_fix),
            'fixed': len(fixed),
            'failed': len(failed)
        }
    }


def auto_fix_local_links(folder_path, broken_links):
    """
    Автоматически исправляет все ссылки которые можно исправить локально.
    """
    # Анализируем
    analysis = analyze_broken_links(folder_path, broken_links)
    
    # Исправляем те что можно
    if analysis['fixable_local']:
        fix_result = fix_broken_links(folder_path, analysis['fixable_local'])
    else:
        fix_result = {'fixed': [], 'failed': [], 'summary': {'total': 0, 'fixed': 0, 'failed': 0}}
    
    return {
        'analysis': analysis,
        'fix_result': fix_result,
        'need_download': analysis['need_download'],
        'unfixable': analysis['unfixable']
    }
