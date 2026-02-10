FROM python:3.11-slim

# Метаданные
LABEL maintainer="canteen-plus"
LABEL description="Система управления школьной столовой"

# Рабочая директория
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаём директорию для базы данных
RUN mkdir -p /app/data

# Открываем порт
EXPOSE 8080

# Переменные окружения
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Запускаем приложение
CMD ["python", "app.py"]