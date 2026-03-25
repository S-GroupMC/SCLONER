"""
Общие константы и паттерны для всех модулей.
Централизованное хранение для избежания дубликатов.
"""

# HTTP заголовки по умолчанию
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# Таймауты по умолчанию
DEFAULT_TIMEOUT = 15
DEFAULT_CONNECT_TIMEOUT = 10

# =============================================================================
# ПАТТЕРНЫ ТРЕКЕРОВ - НЕ скачивать
# =============================================================================
TRACKER_PATTERNS = [
    # Google
    'google-analytics', 'googletagmanager', 'googlesyndication',
    'googleadservices', 'doubleclick', 'gstatic.com/recaptcha',
    # Facebook
    'facebook', 'fbcdn', 'fb.com', 'connect.facebook',
    # Analytics
    'hotjar', 'mixpanel', 'segment', 'amplitude', 'heap',
    'fullstory', 'logrocket', 'mouseflow', 'crazyegg',
    # Chat/Support
    'intercom', 'crisp', 'drift', 'tawk', 'zendesk', 'freshdesk',
    # Marketing
    'hubspot', 'marketo', 'pardot', 'salesforce', 'mailchimp',
    'klaviyo', 'sendgrid', 'mailgun',
    # Other trackers
    'cloudflareinsights', 'clarity.ms', 'mc.yandex', 'metrika',
    'pixel', 'tracking', 'analytics', 'cdn-cgi/beacon',
    'newrelic', 'sentry', 'bugsnag', 'rollbar',
    # Ad networks
    'adsense', 'adroll', 'criteo', 'taboola', 'outbrain'
]

# =============================================================================
# ПАТТЕРНЫ CDN
# =============================================================================

# CDN которые ОБЯЗАТЕЛЬНО нужно скачать (ресурсы сайта)
REQUIRED_CDN_PATTERNS = [
    'cdn', 'static', 'assets', 'images', 'img', 'media', 'fonts',
    'cloudfront.net',      # AWS CloudFront
    's3.amazonaws.com',    # AWS S3
    's3-',                 # AWS S3 regional
    'storage.googleapis.com',  # Google Cloud Storage
    'blob.core.windows.net',   # Azure Blob Storage
    'wp-content',          # WordPress
    'uploads',             # Загруженные файлы
    'files',               # Файлы
    'resources',           # Ресурсы
]

# CDN которые можно НЕ скачивать (публичные библиотеки)
OPTIONAL_CDN_PATTERNS = [
    'jsdelivr.net',        # npm CDN
    'www.jsdelivr.com',    # Сайт jsdelivr (не CDN!)
    'unpkg.com',           # npm CDN
    'cdnjs.cloudflare.com',  # JS библиотеки
    'bootstrapcdn.com',    # Bootstrap
    'code.jquery.com',     # jQuery
    'fonts.googleapis.com',  # Google Fonts CSS
    'fonts.gstatic.com',   # Google Fonts файлы
    'use.fontawesome.com', # FontAwesome
    'kit.fontawesome.com', # FontAwesome Kit
    'ajax.googleapis.com', # Google Ajax libs
    'maxcdn.bootstrapcdn.com',  # Bootstrap MaxCDN
]

# Все CDN паттерны
CDN_PATTERNS = [
    'cdn', 'static', 'assets', 'images', 'img', 'media', 'fonts',
    'cloudfront', 'cloudflare', 'akamai', 'fastly', 'jsdelivr', 'unpkg',
    'googleapis', 'gstatic', 'bootstrapcdn', 'jquery', 'cdnjs'
]

# =============================================================================
# РАСШИРЕНИЯ ФАЙЛОВ
# =============================================================================

# HTML файлы
HTML_EXTENSIONS = ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp']

# Скрипты и стили
SCRIPT_EXTENSIONS = ['.js', '.mjs', '.jsx', '.ts', '.tsx']
STYLE_EXTENSIONS = ['.css', '.scss', '.sass', '.less']

# Изображения
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.avif', '.bmp', '.tiff']

# Шрифты
FONT_EXTENSIONS = ['.woff', '.woff2', '.ttf', '.eot', '.otf']

# Медиа
MEDIA_EXTENSIONS = ['.mp4', '.webm', '.mp3', '.ogg', '.wav', '.avi', '.mov']

# Данные
DATA_EXTENSIONS = ['.json', '.xml', '.csv', '.txt']

# Все скачиваемые расширения
DOWNLOAD_EXTENSIONS = (
    SCRIPT_EXTENSIONS + STYLE_EXTENSIONS + 
    IMAGE_EXTENSIONS + FONT_EXTENSIONS + 
    MEDIA_EXTENSIONS + DATA_EXTENSIONS +
    HTML_EXTENSIONS + ['.pdf', '.zip']
)

# =============================================================================
# HTTP СТАТУС КОДЫ
# =============================================================================

STATUS_DESCRIPTIONS = {
    200: 'OK',
    201: 'Created',
    204: 'No Content',
    301: 'Moved Permanently (редирект)',
    302: 'Found (временный редирект)',
    303: 'See Other',
    304: 'Not Modified',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden (доступ запрещён)',
    404: 'Not Found (страница не найдена)',
    405: 'Method Not Allowed',
    408: 'Request Timeout',
    410: 'Gone (страница удалена)',
    429: 'Too Many Requests',
    500: 'Internal Server Error',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout'
}

# =============================================================================
# ПРИЧИНЫ ОШИБОК
# =============================================================================

ERROR_REASONS = {
    'deleted': 'Страница удалена с сервера',
    'moved': 'Страница перемещена (редирект)',
    'typo': 'Опечатка в URL',
    'broken_link': 'Битая ссылка в исходном HTML',
    'dynamic': 'Динамически генерируемая страница',
    'protected': 'Страница защищена (требует авторизации)',
    'external': 'Внешний ресурс недоступен',
    'timeout': 'Таймаут при загрузке',
    'rate_limit': 'Превышен лимит запросов',
    'server_error': 'Ошибка сервера',
    'unknown': 'Причина неизвестна'
}

# =============================================================================
# УТИЛИТЫ
# =============================================================================

def is_tracker(url):
    """Проверяет является ли URL трекером"""
    url_lower = url.lower()
    return any(pattern in url_lower for pattern in TRACKER_PATTERNS)


def is_required_cdn(domain):
    """Проверяет является ли домен обязательным CDN"""
    domain_lower = domain.lower()
    # Сначала проверяем опциональные (они более специфичны)
    if any(opt in domain_lower for opt in OPTIONAL_CDN_PATTERNS):
        return False
    return any(req in domain_lower for req in REQUIRED_CDN_PATTERNS)


def is_cdn(domain):
    """Проверяет является ли домен CDN"""
    domain_lower = domain.lower()
    return any(cdn in domain_lower for cdn in CDN_PATTERNS)


def get_file_type(path):
    """Определяет тип файла по расширению"""
    path_lower = path.lower()
    
    if any(path_lower.endswith(ext) for ext in HTML_EXTENSIONS) or path_lower.endswith('/'):
        return 'page'
    elif any(path_lower.endswith(ext) for ext in SCRIPT_EXTENSIONS):
        return 'script'
    elif any(path_lower.endswith(ext) for ext in STYLE_EXTENSIONS):
        return 'style'
    elif any(path_lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return 'image'
    elif any(path_lower.endswith(ext) for ext in FONT_EXTENSIONS):
        return 'font'
    elif any(path_lower.endswith(ext) for ext in MEDIA_EXTENSIONS):
        return 'media'
    elif any(path_lower.endswith(ext) for ext in DATA_EXTENSIONS):
        return 'data'
    else:
        return 'other'


def normalize_domain(domain):
    """Убирает www. префикс для сравнения"""
    return domain.lower().lstrip('www.')


def get_root_domain(domain):
    """Извлекает корневой домен (example.com из sub.example.com)"""
    domain = normalize_domain(domain)
    parts = domain.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return domain


def is_valid_domain(domain):
    """Проверяет валидность домена"""
    if not domain:
        return False
    # Должен содержать точку и не содержать :
    if ':' in domain or '.' not in domain:
        return False
    # Пропускаем localhost и IP
    if domain in ('localhost', '127.0.0.1') or domain.startswith('192.168.'):
        return False
    return True
