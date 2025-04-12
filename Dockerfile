FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для Postgres и других библиотек
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов с зависимостями и установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY . .

# Определение переменных окружения
ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONPATH=/app

# Экспонирование порта
EXPOSE 8000

# Запуск FastAPI приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 