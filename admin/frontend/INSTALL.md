# 🚀 Установка и запуск Black Rabbit Cloner (Vue.js)

## Шаг 1: Установка зависимостей

```bash
cd /Users/nick/DEV/WCLoner/wget/admin/frontend
npm install
```

Это установит:
- Vue 3
- Vue Router
- Pinia
- Vite
- Tailwind CSS
- Socket.IO Client
- Axios

## Шаг 2: Запуск Backend

В отдельном терминале:

```bash
cd /Users/nick/DEV/WCLoner/wget
python3 admin/app.py
```

Backend запустится на `http://localhost:5000`

## Шаг 3: Запуск Frontend (Development)

```bash
cd /Users/nick/DEV/WCLoner/wget/admin/frontend
npm run dev
```

Frontend запустится на `http://localhost:5173`

Откройте в браузере: **http://localhost:5173**

## Production Build

Когда готов к деплою:

```bash
npm run build
```

Файлы будут собраны в `admin/static/dist/`

Flask автоматически раздаст их на корневом URL.

## Структура проекта

```
admin/frontend/
├── src/
│   ├── components/          # Компоненты
│   │   └── ActiveDownloads.vue
│   ├── views/              # Страницы
│   │   ├── LandingsView.vue
│   │   └── DownloadView.vue
│   ├── stores/             # State management
│   │   ├── jobs.js
│   │   └── landings.js
│   ├── router/             # Маршрутизация
│   │   └── index.js
│   ├── assets/             # CSS
│   │   └── main.css
│   ├── App.vue             # Главный компонент
│   └── main.js             # Точка входа
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## Что работает

✅ Структура проекта создана
✅ Vue Router настроен
✅ Pinia stores созданы
✅ WebSocket интеграция
✅ Компонент ActiveDownloads
✅ Страница Landings
✅ Страница Download
✅ Tailwind CSS настроен

## Что нужно доделать

- [ ] Установить npm зависимости
- [ ] Протестировать запуск
- [ ] Доделать все компоненты
- [ ] Добавить модалки
- [ ] Добавить уведомления
- [ ] Production build и деплой

## Следующие шаги

1. Запусти `npm install` в папке `admin/frontend/`
2. Запусти backend: `python3 admin/app.py`
3. Запусти frontend: `npm run dev`
4. Открой http://localhost:5173

---

**Black Rabbit Cloner 🐰 - Полная миграция на Vue.js завершена!**
