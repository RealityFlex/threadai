FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для Postgres и других библиотек
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка poetry для управления зависимостями
RUN pip install --no-cache-dir poetry

# Копирование только файлов зависимостей для оптимизации кэширования слоев Docker
COPY requirements.txt .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY . .

# Определение переменных окружения
ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Проверка работоспособности приложения
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Экспонирование порта
EXPOSE 8000

# Запуск FastAPI приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"] 