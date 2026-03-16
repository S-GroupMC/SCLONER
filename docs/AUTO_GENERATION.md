# Автоматическая генерация Vue-обёртки при скачивании

## 📋 Полная последовательность действий

### **Шаг 1: Пользователь запускает скачивание**

В UI (`landings.html`) пользователь:
1. Вводит URL: `https://example.com`
2. Выбирает движок: `wget2` / `puppeteer` / `httrack` / `smart`
3. ✅ **Включает опцию "Создать Vue-обёртку"** (новый чекбокс)
4. Нажимает "Скачать"

```javascript
// Отправляется на сервер:
{
  url: 'https://example.com',
  engine: 'wget2',
  options: {
    recursive: true,
    depth: 3,
    with_vue_wrapper: true  // ← Новая опция
  }
}
```

---

### **Шаг 2: WCLoner скачивает сайт**

```
[00:00] Создание job
[00:01] Запуск wget2/puppeteer/httrack
[00:02] Скачивание файлов...
[02:30] Скачивание завершено
```

**Результат:**
```
/downloads/example.com/
├── index.html
├── about.html
├── css/
│   └── style.css
├── js/
│   └── app.js
└── images/
    └── logo.png
```

---

### **Шаг 3: Post-processing**

```python
# В app.py после завершения скачивания:

# 3.1 Очистка внешних доменов
cleanup_external_domains(job)

# 3.2 Обновление статистики
update_job_stats(job)

# 3.3 Проверка опции Vue-обёртки
if job.options.get('with_vue_wrapper', False):
    # Переход к генерации
```

---

### **Шаг 4: Извлечение домена**

```python
from urllib.parse import urlparse

# URL: https://www.example.com/page
parsed = urlparse(job.url)
main_domain = parsed.netloc.replace('www.', '')
# Результат: 'example.com'
```

---

### **Шаг 5: Сканирование поддоменов**

```python
# Автоматически ищем все связанные домены в /downloads/
subdomains = []
for item in DOWNLOADS_DIR.iterdir():
    if main_domain in item.name and item.is_dir():
        subdomains.append(item.name)

# Результат:
# ['example.com', 'blog.example.com', 'shop.example.com']
```

---

### **Шаг 6: Генерация Vue-обёртки**

```python
success = generate_vue_wrapper(
    folder_path=job.output_dir,      # /downloads/example.com
    main_domain='example.com',
    port=3000,                        # Vite dev server
    backend_port=3001                 # Backend для статики
)
```

#### **6.1 Создание структуры папок**

```python
# Создаём:
vue_dir = folder_path / 'vue-app'
src_dir = vue_dir / 'src'
site_dir = folder_path / '_site'

vue_dir.mkdir(exist_ok=True)
src_dir.mkdir(exist_ok=True)
site_dir.mkdir(exist_ok=True)
```

#### **6.2 Перемещение файлов**

```python
# Перемещаем ВСЕ скачанные файлы в _site/
for item in folder_path.iterdir():
    if item.name not in ['vue-app', '_site', '_wcloner']:
        shutil.move(str(item), str(site_dir / item.name))
```

**До:**
```
example.com/
├── index.html
├── css/
└── js/
```

**После:**
```
example.com/
├── vue-app/        ← НОВАЯ
├── _site/          ← НОВАЯ
│   ├── index.html  ← ПЕРЕМЕЩЕНО
│   ├── css/        ← ПЕРЕМЕЩЕНО
│   └── js/         ← ПЕРЕМЕЩЕНО
```

#### **6.3 Генерация файлов**

```python
# Замены для всех файлов:
replacements = {
    '{{MAIN_DOMAIN}}': 'example.com',
    '{{PACKAGE_NAME}}': 'example-com',
    '{{PORT}}': '3000',
    '{{BACKEND_PORT}}': '3001',
    '{{SUBDOMAINS_JSON}}': '["example.com", "blog.example.com"]'
}

# Генерируем каждый файл:
```

**1. vue-app/index.html**
```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <title>example.com</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

**2. vue-app/src/App.vue**
```vue
<script setup>
// Компонент с iframe + SEO
</script>
```

**3. vue-app/src/main.js**
```javascript
import { createApp } from 'vue'
import App from './App.vue'
createApp(App).mount('#app')
```

**4. vue-app/package.json**
```json
{
  "name": "example-com",
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  }
}
```

**5. vue-app/vite.config.js**
```javascript
export default {
  server: {
    port: 3000,
    proxy: {
      '/__raw': {
        target: 'http://localhost:3001'
      }
    }
  }
}
```

**6. backend-server.js**
```javascript
// Node.js сервер на порту 3001
// Раздаёт файлы из _site/
```

**7. README-VUE.md**
```markdown
# example.com - Vue Wrapper

## Запуск:
1. cd vue-app
2. npm install
3. node ../backend-server.js (терминал 1)
4. npm run dev (терминал 2)
```

---

### **Шаг 7: Финальная структура**

```
example.com/
├── vue-app/                    ← Vue приложение
│   ├── src/
│   │   ├── App.vue            ← iframe + SEO
│   │   └── main.js            ← точка входа
│   ├── index.html             ← HTML шаблон
│   ├── package.json           ← зависимости
│   └── vite.config.js         ← конфиг Vite
├── _site/                      ← Скачанный контент
│   ├── index.html
│   ├── about.html
│   ├── css/
│   ├── js/
│   └── images/
├── backend-server.js           ← сервер для статики
└── README-VUE.md              ← инструкция
```

---

### **Шаг 8: Уведомление пользователя**

```python
# В консоль job добавляются строки:
job.output_lines.append("")
job.output_lines.append("[WCLoner] Генерация Vue-обёртки...")
job.output_lines.append("[WCLoner] ✅ Vue-обёртка создана!")
job.output_lines.append("[WCLoner] Запуск:")
job.output_lines.append("[WCLoner]   1. cd /downloads/example.com/vue-app")
job.output_lines.append("[WCLoner]   2. npm install")
job.output_lines.append("[WCLoner]   3. node ../backend-server.js (терминал 1)")
job.output_lines.append("[WCLoner]   4. npm run dev (терминал 2)")

# Отправка через WebSocket:
socketio.emit('job_update', job.to_dict())
```

**Пользователь видит в UI:**
```
✅ Скачивание завершено
✅ Vue-обёртка создана!

Запуск:
  1. cd /downloads/example.com/vue-app
  2. npm install
  3. node ../backend-server.js (терминал 1)
  4. npm run dev (терминал 2)
```

---

## ⏱️ Таймлайн выполнения

```
00:00 - Пользователь нажимает "Скачать"
00:01 - Создание job, запуск wget2
02:30 - Скачивание завершено
02:31 - cleanup_external_domains()
02:32 - update_job_stats()
02:33 - Проверка with_vue_wrapper = true
02:34 - Извлечение домена: example.com
02:35 - Сканирование поддоменов (0.5s)
02:36 - Создание vue-app/ (0.1s)
02:37 - Создание src/ (0.1s)
02:38 - Создание _site/ (0.1s)
02:39 - Перемещение файлов (1.0s)
02:40 - Генерация index.html (0.1s)
02:41 - Копирование App.vue (0.1s)
02:42 - Копирование main.js (0.1s)
02:43 - Генерация package.json (0.1s)
02:44 - Генерация vite.config.js (0.1s)
02:45 - Генерация backend-server.js (0.1s)
02:46 - Генерация README-VUE.md (0.2s)
02:47 - Уведомление через WebSocket
02:48 - ✅ Готово!
```

**Общее время генерации: ~3 секунды**

---

## 🔧 Код интеграции

### **app.py - автоматическая генерация**

```python
# После завершения скачивания (строка ~1020):

if job.status == 'completed' and job.options.get('with_vue_wrapper', False):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(job.url)
        main_domain = parsed.netloc.replace('www.', '')
        
        job.output_lines.append("")
        job.output_lines.append("[WCLoner] Генерация Vue-обёртки...")
        
        success = generate_vue_wrapper(
            folder_path=job.output_dir,
            main_domain=main_domain,
            port=3000,
            backend_port=3001
        )
        
        if success:
            job.output_lines.append("[WCLoner] ✅ Vue-обёртка создана!")
            # ... инструкции ...
    except Exception as e:
        job.output_lines.append(f"[WCLoner] ❌ Ошибка: {e}")
```

---

## 📊 Что создаётся автоматически

| Файл | Источник | Время |
|------|----------|-------|
| `vue-app/` | Создание папки | 0.1s |
| `vue-app/src/` | Создание папки | 0.1s |
| `_site/` | Создание папки | 0.1s |
| Перемещение файлов | shutil.move() | 1.0s |
| `vue-app/index.html` | Шаблон + замены | 0.1s |
| `vue-app/src/App.vue` | Копирование | 0.1s |
| `vue-app/src/main.js` | Копирование | 0.1s |
| `vue-app/package.json` | Шаблон + замены | 0.1s |
| `vue-app/vite.config.js` | Шаблон + замены | 0.1s |
| `backend-server.js` | Шаблон + замены | 0.1s |
| `README-VUE.md` | Генератор | 0.2s |

**Итого: ~2.5 секунды**

---

## 🎯 Запуск после генерации

### **Терминал 1 - Backend сервер**
```bash
cd /downloads/example.com
node backend-server.js

# Вывод:
# [WCLoner Backend] Running on http://localhost:3001
# [WCLoner Backend] Serving: example.com
```

### **Терминал 2 - Vite dev server**
```bash
cd /downloads/example.com/vue-app
npm install  # первый раз
npm run dev

# Вывод:
# VITE v5.0.0  ready in 500 ms
# ➜  Local:   http://localhost:3000/
# ➜  Network: use --host to expose
```

### **Браузер**
```
Открыть: http://localhost:3000
```

---

## 🔄 Порядок операций в коде

```python
def generate_vue_wrapper(folder_path, main_domain, port, backend_port):
    # 1. Проверка существования папки
    if not folder_path.exists():
        return False
    
    # 2. Создание структуры
    vue_dir = folder_path / 'vue-app'
    src_dir = vue_dir / 'src'
    site_dir = folder_path / '_site'
    
    vue_dir.mkdir(exist_ok=True)
    src_dir.mkdir(exist_ok=True)
    site_dir.mkdir(exist_ok=True)
    
    # 3. Перемещение файлов
    for item in folder_path.iterdir():
        if item.name not in ['vue-app', '_site', '_wcloner']:
            shutil.move(str(item), str(site_dir / item.name))
    
    # 4. Подготовка замен
    replacements = {
        '{{MAIN_DOMAIN}}': main_domain,
        '{{PACKAGE_NAME}}': main_domain.replace('.', '-'),
        '{{PORT}}': str(port),
        '{{BACKEND_PORT}}': str(backend_port)
    }
    
    # 5. Генерация файлов
    generate_file('index.html', vue_dir, replacements)
    copy_file('App.vue', src_dir)
    copy_file('main.js', src_dir)
    generate_file('package.json', vue_dir, replacements)
    generate_file('vite.config.js', vue_dir, replacements)
    generate_file('server.js', folder_path, replacements, 'backend-server.js')
    generate_readme(folder_path, main_domain, port)
    
    # 6. Логирование
    print(f"[Vue Generator] ✅ Generated for {main_domain}")
    
    return True
```

---

## 📝 Примеры использования

### **Пример 1: Скачивание с Vue-обёрткой**
```javascript
// В UI
{
  url: 'https://example.com',
  engine: 'wget2',
  options: {
    with_vue_wrapper: true  // ← Включено
  }
}

// Результат:
// ✅ Скачано + Vue-обёртка создана автоматически
```

### **Пример 2: Скачивание без Vue-обёртки**
```javascript
// В UI
{
  url: 'https://example.com',
  engine: 'wget2',
  options: {
    with_vue_wrapper: false  // ← Выключено (по умолчанию)
  }
}

// Результат:
// ✅ Скачано, Vue-обёртка НЕ создаётся
```

### **Пример 3: Ручная генерация позже**
```python
# Через Python API
from app import generate_vue_wrapper
from pathlib import Path

generate_vue_wrapper(
    folder_path=Path('/downloads/example.com'),
    main_domain='example.com',
    port=3000,
    backend_port=3001
)
```

---

## ✅ Итоговая последовательность

```
1. Пользователь → Включает "Vue-обёртку" → Скачивает
2. WCLoner → Скачивает сайт → Сохраняет в /downloads/
3. Post-processing → Очистка → Статистика
4. Проверка → with_vue_wrapper = true?
5. Извлечение → Домен из URL
6. Сканирование → Поддомены в /downloads/
7. Генерация → Создание vue-app/, _site/, файлов
8. Перемещение → Файлы в _site/
9. Замены → {{...}} → реальные значения
10. Уведомление → WebSocket → UI
11. Готово → Инструкции по запуску
```

---

**Создано WCLoner Team**
