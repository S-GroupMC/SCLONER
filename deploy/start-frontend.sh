#!/bin/bash

# Скрипт запуска Black Rabbit Cloner (Vue.js + FastAPI Backend)
# Использование: ./start-frontend.sh [режим]
# Режимы: dev (по умолчанию), prod, backend-only, frontend-only

MODE=${1:-dev}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ADMIN_DIR="$PROJECT_DIR/admin"
FRONTEND_DIR="$ADMIN_DIR/frontend"

BACKEND_PORT=9000
FRONTEND_PORT=5173

echo "=========================================="
echo "  🐰 Black Rabbit Cloner"
echo "  Режим: $MODE"
echo "=========================================="

# Функция остановки процессов при выходе
cleanup() {
    echo ""
    echo "Остановка серверов..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Функция запуска backend
start_backend() {
    echo ""
    echo "📡 Запуск Backend (FastAPI + Uvicorn)..."
    echo "   Порт: $BACKEND_PORT"
    
    cd "$ADMIN_DIR"
    
    # Активация виртуального окружения если есть
    if [ -d "venv" ]; then
        echo "   Активация venv..."
        source venv/bin/activate
    fi
    
    # Проверка зависимостей
    if [ -f "requirements.txt" ]; then
        echo "   Проверка Python зависимостей..."
        pip install -q -r requirements.txt
    fi
    
    # Освобождение порта если занят
    if lsof -ti:$BACKEND_PORT > /dev/null 2>&1; then
        echo "   Порт $BACKEND_PORT занят, освобождаем..."
        lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null
        sleep 1
    fi
    
    echo "   ✅ Backend запущен на http://localhost:$BACKEND_PORT"
    python app.py &
    BACKEND_PID=$!
}

# Функция запуска frontend (dev mode)
start_frontend_dev() {
    echo ""
    echo "🎨 Запуск Frontend (Vue.js Dev Server)..."
    echo "   Порт: $FRONTEND_PORT"
    
    cd "$FRONTEND_DIR"
    
    # Проверка node_modules
    if [ ! -d "node_modules" ]; then
        echo "   📦 Установка npm зависимостей..."
        npm install
    fi
    
    # Освобождение порта если занят
    if lsof -ti:$FRONTEND_PORT > /dev/null 2>&1; then
        echo "   Порт $FRONTEND_PORT занят, освобождаем..."
        lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null
        sleep 1
    fi
    
    echo "   ✅ Frontend запущен на http://localhost:$FRONTEND_PORT"
    npm run dev &
    FRONTEND_PID=$!
}

# Функция сборки production
build_frontend() {
    echo ""
    echo "🏗️  Сборка Frontend для Production..."
    
    cd "$FRONTEND_DIR"
    
    # Проверка node_modules
    if [ ! -d "node_modules" ]; then
        echo "   📦 Установка npm зависимостей..."
        npm install
    fi
    
    echo "   🔨 Запуск build..."
    npm run build
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Build завершён успешно!"
        echo "   📁 Файлы в: $ADMIN_DIR/static/dist/"
    else
        echo "   ❌ Ошибка сборки!"
        exit 1
    fi
}

# Основная логика
case "$MODE" in
    dev)
        echo ""
        echo "🚀 Режим разработки (Backend + Frontend Dev Server)"
        echo ""
        
        start_backend
        sleep 2
        start_frontend_dev
        sleep 3
        
        echo ""
        echo "=========================================="
        echo "  ✅ Серверы запущены!"
        echo "=========================================="
        echo "  Backend:  http://localhost:$BACKEND_PORT"
        echo "  Frontend: http://localhost:$FRONTEND_PORT"
        echo "=========================================="
        echo ""
        echo "  Откройте в браузере:"
        echo "  👉 http://localhost:$FRONTEND_PORT"
        echo ""
        echo "  Нажмите Ctrl+C для остановки"
        echo "=========================================="
        
        # Открытие браузера
        (sleep 2 && open "http://localhost:$FRONTEND_PORT") &
        
        # Ожидание завершения
        wait
        ;;
        
    prod)
        echo ""
        echo "🏭 Режим production (Backend + Static Build)"
        echo ""
        
        build_frontend
        start_backend
        
        echo ""
        echo "=========================================="
        echo "  ✅ Production сервер запущен!"
        echo "=========================================="
        echo "  URL: http://localhost:$BACKEND_PORT"
        echo "=========================================="
        echo ""
        echo "  Откройте в браузере:"
        echo "  👉 http://localhost:$BACKEND_PORT"
        echo ""
        echo "  Нажмите Ctrl+C для остановки"
        echo "=========================================="
        
        # Открытие браузера
        (sleep 2 && open "http://localhost:$BACKEND_PORT") &
        
        wait
        ;;
        
    backend-only)
        echo ""
        echo "📡 Запуск только Backend"
        echo ""
        
        start_backend
        
        echo ""
        echo "=========================================="
        echo "  ✅ Backend запущен!"
        echo "=========================================="
        echo "  URL: http://localhost:$BACKEND_PORT"
        echo "=========================================="
        
        wait
        ;;
        
    frontend-only)
        echo ""
        echo "🎨 Запуск только Frontend Dev Server"
        echo ""
        
        start_frontend_dev
        
        echo ""
        echo "=========================================="
        echo "  ✅ Frontend запущен!"
        echo "=========================================="
        echo "  URL: http://localhost:$FRONTEND_PORT"
        echo "=========================================="
        echo ""
        echo "  ⚠️  Убедитесь что Backend запущен отдельно!"
        echo "=========================================="
        
        # Открытие браузера
        (sleep 2 && open "http://localhost:$FRONTEND_PORT") &
        
        wait
        ;;
        
    build)
        build_frontend
        ;;
        
    *)
        echo "❌ Неизвестный режим: $MODE"
        echo ""
        echo "Доступные режимы:"
        echo "  dev            - Разработка (Backend + Frontend Dev)"
        echo "  prod           - Production (Backend + Static Build)"
        echo "  backend-only   - Только Backend"
        echo "  frontend-only  - Только Frontend Dev"
        echo "  build          - Только сборка Frontend"
        echo ""
        echo "Использование:"
        echo "  ./start-frontend.sh [режим]"
        exit 1
        ;;
esac
