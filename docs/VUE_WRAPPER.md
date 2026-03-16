# Vue Wrapper для скачанных сайтов

## 📋 Обзор

WCLoner теперь может создавать Vue.js обёртку для каждого скачанного сайта. Это позволяет:

- ✅ **SEO оптимизация** - извлечение meta tags, structured data
- ✅ **Изоляция контента** - статический HTML в iframe
- ✅ **Синхронизация URL** - навигация между iframe и родителем
- ✅ **Трекинг и аналитика** - инжекция скриптов
- ✅ **Hot Module Replacement** - быстрая разработка

## 🏗️ Структура проекта

После генерации Vue-обёртки структура папки будет:

```
example.com/
├── vue-app/                    ← Vue приложение
│   ├── src/
│   │   ├── App.vue            ← Главный компонент с iframe
│   │   └── main.js            ← Точка входа
│   ├── index.html             ← HTML шаблон
│   ├── package.json           ← Зависимости
│   └── vite.config.js         ← Конфигурация Vite
├── _site/                      ← Скачанный контент (перемещён)
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── images/
├── backend-server.js           ← Node.js сервер для статики
└── README-VUE.md              ← Инструкция
```

## 🚀 Использование

### Автоматическая генерация

При скачивании сайта через WCLoner:

```python
# В app.py после завершения скачивания
generate_server_files(
    folder_path='/path/to/downloads/example.com',
    main_domain='example.com',
    port=3000,
    with_vue=True  # ← Включить Vue-обёртку
)
```

### Ручная генерация

```python
from pathlib import Path
from app import generate_vue_wrapper

generate_vue_wrapper(
    folder_path=Path('/path/to/downloads/example.com'),
    main_domain='example.com',
    port=3000,          # Vite dev server
    backend_port=3001   # Backend для статики
)
```

## 📦 Установка и запуск

### 1. Установка зависимостей

```bash
cd example.com/vue-app
npm install
```

Установит:
- `vue@^3.4.0` - Vue.js 3
- `vue-router@^4.2.0` - Роутинг
- `vite@^5.0.0` - Сборщик
- `@vitejs/plugin-vue@^5.0.0` - Vite плагин для Vue

### 2. Запуск в режиме разработки

Откройте **два терминала**:

**Терминал 1** - Backend сервер (порт 3001):
```bash
cd example.com
node backend-server.js
```

**Терминал 2** - Vite dev server (порт 3000):
```bash
cd example.com/vue-app
npm run dev
```

Откройте браузер: **http://localhost:3000**

### 3. Production сборка

```bash
cd vue-app
npm run build
```

Результат в `vue-app/dist/` - готовые статические файлы для деплоя.

## 🔧 Как это работает

### App.vue - Главный компонент

```vue
<template>
  <div class="wcloner-wrapper">
    <!-- Iframe загружает статический контент -->
    <iframe
      ref="iframeRef"
      :src="iframeSrc"
      @load="onIframeLoad"
    ></iframe>
    
    <!-- Скрытый SEO контент для поисковиков -->
    <div class="seo-content" aria-hidden="true">
      <h1>{{ seoH1 }}</h1>
      <h2 v-for="h2 in seoH2s">{{ h2 }}</h2>
      <p v-for="text in seoTexts">{{ text }}</p>
    </div>
  </div>
</template>
```

**Функции:**
- `resolveIframeSrc()` - формирует URL для iframe (`/__raw/page`)
- `extractSEO()` - извлекает title, meta, headings из iframe
- `updateBrowserUrl()` - синхронизирует URL при навигации в iframe
- `injectTracking()` - добавляет трекинг скрипты в iframe

### Backend Server

```javascript
// backend-server.js
// Слушает на порту 3001
// Раздаёт файлы из _site/
// Обрабатывает запросы /__raw/*
```

### Vite Config

```javascript
// vite.config.js
export default {
  server: {
    port: 3000,
    proxy: {
      '/__raw': {
        target: 'http://localhost:3001',
        changeOrigin: true
      }
    }
  }
}
```

## 🎯 Навигация

### URL структура

```
http://localhost:3000/?page=about
                        ↓
                  iframe загружает
                        ↓
            http://localhost:3001/__raw/about
```

### Синхронизация

1. Пользователь кликает ссылку в iframe
2. `onIframeLoad()` ловит событие
3. `updateBrowserUrl()` обновляет адресную строку
4. Vue Router реагирует на изменение
5. Обновляется `iframeSrc`

## 🔍 SEO оптимизация

### Извлечение контента

```javascript
function extractSEO() {
  const doc = iframe.contentDocument
  
  // Title
  document.title = doc.title
  
  // Meta description
  const metaDesc = doc.querySelector('meta[name="description"]')
  setMetaTag('description', metaDesc.content)
  
  // OG tags
  setMetaTag('og:image', doc.querySelector('meta[property="og:image"]').content)
  
  // Headings для скрытого контента
  seoH1.value = doc.querySelector('h1').textContent
  seoH2s.value = [...doc.querySelectorAll('h2')].map(el => el.textContent)
}
```

### Скрытый контент

```html
<!-- Видим только поисковикам, не пользователям -->
<div class="seo-content" aria-hidden="true" style="position:absolute;left:-9999px">
  <h1>Заголовок страницы</h1>
  <h2>Подзаголовок 1</h2>
  <h2>Подзаголовок 2</h2>
  <p>Текст параграфа...</p>
</div>
```

## 📊 Преимущества vs простой server.js

| Функция | Простой server.js | Vue Wrapper |
|---------|------------------|-------------|
| Запуск | ✅ `node server.js` | ⚠️ 2 команды |
| SEO | ❌ Нет | ✅ Полная оптимизация |
| Трекинг | ❌ Нет | ✅ Инжекция скриптов |
| HMR | ❌ Нет | ✅ Есть |
| Production build | ❌ Нет | ✅ `npm run build` |
| Сложность | ✅ Простой | ⚠️ Требует npm |

## 🛠️ Кастомизация

### Добавление трекинга

Редактируйте `App.vue`:

```javascript
function injectTracking() {
  const doc = iframe.contentDocument
  
  // Google Analytics
  const gaScript = doc.createElement('script')
  gaScript.src = 'https://www.googletagmanager.com/gtag/js?id=GA_ID'
  doc.head.appendChild(gaScript)
  
  // Facebook Pixel
  const fbScript = doc.createElement('script')
  fbScript.textContent = `!function(f,b,e,v,n,t,s){...}`
  doc.head.appendChild(fbScript)
}
```

### Изменение стилей обёртки

```vue
<style scoped>
.wcloner-wrapper {
  /* Добавить header/footer */
  padding-top: 60px;
}

/* Добавить навигацию сверху */
.wcloner-wrapper::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: #000;
  z-index: 1000;
}
</style>
```

## 🐛 Troubleshooting

### Iframe не загружается

**Проблема:** Белый экран в iframe

**Решение:**
1. Проверьте что backend-server.js запущен на порту 3001
2. Проверьте консоль браузера на CORS ошибки
3. Убедитесь что файлы в `_site/` существуют

### SEO не извлекается

**Проблема:** `extractSEO()` не работает

**Причина:** Cross-origin ограничения

**Решение:** Backend и Vite должны быть на одном домене (localhost)

### npm install ошибки

**Проблема:** Не устанавливаются зависимости

**Решение:**
```bash
# Очистить кэш
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

## 📝 Примеры использования

### Пример 1: Базовая генерация

```python
generate_vue_wrapper(
    folder_path=Path('/downloads/example.com'),
    main_domain='example.com'
)
```

### Пример 2: Кастомные порты

```python
generate_vue_wrapper(
    folder_path=Path('/downloads/example.com'),
    main_domain='example.com',
    port=8080,          # Vite
    backend_port=8081   # Backend
)
```

### Пример 3: Массовая генерация

```python
from pathlib import Path

downloads_dir = Path('/downloads')
for site_dir in downloads_dir.iterdir():
    if site_dir.is_dir():
        domain = site_dir.name
        generate_vue_wrapper(site_dir, domain)
```

## 🎓 Дополнительные ресурсы

- [Vue.js документация](https://vuejs.org/)
- [Vite документация](https://vitejs.dev/)
- [Vue Router](https://router.vuejs.org/)

---

**Создано WCLoner Team**
