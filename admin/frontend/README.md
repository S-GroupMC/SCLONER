# Black Rabbit Cloner - Vue.js Frontend

Современный фронтенд на Vue 3 + Vite + Tailwind CSS для Black Rabbit Cloner.

## 🚀 Быстрый старт

### Установка зависимостей

```bash
cd admin/frontend
npm install
```

### Разработка

```bash
# Запустить dev server (http://localhost:5173)
npm run dev
```

Backend должен быть запущен на порту 5000:
```bash
cd ../..
python3 admin/app.py
```

### Production build

```bash
# Собрать для production
npm run build

# Файлы будут в admin/static/dist/
```

## 📁 Структура проекта

```
admin/frontend/
├── src/
│   ├── components/       # Vue компоненты
│   │   ├── ActiveDownloads.vue
│   │   ├── LandingsTable.vue
│   │   └── DownloadForm.vue
│   ├── views/           # Страницы
│   │   ├── LandingsView.vue
│   │   └── DownloadView.vue
│   ├── stores/          # Pinia stores
│   │   ├── jobs.js
│   │   └── landings.js
│   ├── router/          # Vue Router
│   │   └── index.js
│   ├── assets/          # CSS и статика
│   │   └── main.css
│   ├── App.vue          # Главный компонент
│   └── main.js          # Точка входа
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## 🔧 Технологии

- **Vue 3** - Composition API
- **Vite** - Build tool
- **Vue Router** - Маршрутизация
- **Pinia** - State management
- **Tailwind CSS** - Стилизация
- **Socket.IO** - WebSocket для real-time обновлений
- **Axios** - HTTP клиент

## 📡 API интеграция

Все API запросы проксируются через Vite dev server:
- `/api/*` → `http://localhost:5000/api/*`
- `/socket.io/*` → `http://localhost:5000/socket.io/*`

## 🎨 Компоненты

### ActiveDownloads
Виджет активных загрузок с real-time обновлениями через WebSocket.

### LandingsTable
Таблица скачанных сайтов с фильтрацией и действиями.

### DownloadForm
Форма для запуска новых загрузок с настройками.

## 🔄 State Management

### Jobs Store
Управление задачами скачивания:
- `activeJobs` - активные загрузки
- `completedJobs` - завершённые
- `startJob()` - запустить
- `stopJob()` - остановить
- `pauseJob()` - пауза
- `resumeJob()` - продолжить

### Landings Store
Управление скачанными сайтами:
- `landings` - список сайтов
- `loadLandings()` - загрузить
- `deleteFolder()` - удалить
- `checkChanges()` - проверить изменения

## 🚢 Деплой

1. Собрать production build:
```bash
npm run build
```

2. Файлы будут в `admin/static/dist/`

3. Flask автоматически раздаёт их на `/`

## 📝 TODO

- [ ] Завершить все компоненты
- [ ] Добавить модалки (лог, настройки)
- [ ] Добавить фильтрацию и сортировку
- [ ] Добавить темную тему
- [ ] Добавить уведомления (toast)
- [ ] Оптимизировать production build

---

**Создано для Black Rabbit Cloner 🐰**
