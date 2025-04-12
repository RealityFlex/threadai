import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import re

# Загружаем переменные окружения
load_dotenv()

# Получаем URL базы данных из переменных окружения или используем значение по умолчанию
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://threaducation_user:threads_t0_masses@62.109.26.235:5432/education_db"
)

# Выводим информацию о подключении (без пароля) для отладки
try:
    # Используем регулярное выражение для безопасного парсинга строки подключения
    pattern = r"(.*?)://(.*?):(.*?)@(.*)"
    match = re.match(pattern, DATABASE_URL)
    if match:
        protocol, username, _, host_info = match.groups()
        print(f"Connecting to database: {protocol}://{username}@{host_info}")
    else:
        print(f"Connecting to database: {DATABASE_URL}")
except Exception as e:
    # В случае ошибки парсинга просто выводим сообщение без деталей
    print(f"Connecting to database (URL parsing error: {str(e)})")

# Создание движка SQLAlchemy
engine = create_engine(DATABASE_URL)

# Создание сессии
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создание базового класса для моделей
Base = declarative_base()

# Функция-зависимость для FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 