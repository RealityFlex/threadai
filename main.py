from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app import routes
import uvicorn
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
import doc_rec
from fastapi.middleware.cors import CORSMiddleware

from app.utils.exception_handlers import (
    sqlalchemy_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.utils.middleware import LoggingMiddleware
from app.db.database import Base, engine

# Создаем все таблицы, если они не существуют
# В реальном приложении это лучше делать через миграции
# Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Threads API", 
    description="API для работы с постами и комментариями",
    version="1.0.0"
)

# Настройка CORS для всех доменов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Добавляем middleware для логирования
app.add_middleware(LoggingMiddleware)

# Регистрируем обработчики исключений
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(ValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Подключаем маршруты
app.include_router(routes.router)
app.include_router(doc_rec.router)  # Добавляем маршруты для оценки документов

# Простой эндпоинт для проверки состояния сервера
@app.get("/health", tags=["Система"])
async def health_check():
    """Проверка работоспособности API"""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

