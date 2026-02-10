#!/bin/bash

# Скрипт быстрого запуска Docker для Питание+

echo "=============================="
echo "🐳 Запуск Питание+ в Docker"
echo "=============================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Проверка наличия файлов
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Файл docker-compose.yml не найден!"
    echo "Убедитесь что вы находитесь в правильной папке"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "❌ Файл requirements.txt не найден!"
    exit 1
fi

if [ ! -f "app.py" ]; then
    echo "❌ Файл app.py не найден!"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Создаём из .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Файл .env создан. Отредактируйте его перед запуском!"
        exit 0
    else
        echo "❌ Файл .env.example тоже не найден!"
        exit 1
    fi
fi

# Создаём папки если их нет
mkdir -p data logs

echo ""
echo "📦 Останавливаем старые контейнеры..."
docker-compose down

echo ""
echo "🔨 Собираем образ (это может занять несколько минут)..."
docker-compose build --no-cache

echo ""
echo "🚀 Запускаем контейнеры..."
docker-compose up -d

echo ""
echo "⏳ Ждём запуска приложения (10 сек)..."
sleep 10

echo ""
echo "📊 Проверяем статус контейнеров:"
docker-compose ps

echo ""
echo "=============================="
echo "✅ Готово!"
echo "=============================="
echo ""
echo "🌐 Откройте браузер:"
echo "   http://localhost:8080"
echo ""
echo "📝 Полезные команды:"
echo "   docker-compose logs -f        # Смотреть логи"
echo "   docker-compose down           # Остановить"
echo "   docker-compose restart        # Перезапустить"
echo "   docker-compose ps             # Статус"
echo ""
echo "=============================="