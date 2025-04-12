import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем URL базы данных из переменных окружения или используем значение по умолчанию
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://threaducation_user:threads_t0_masses@62.109.26.235:5432/education_db"
)

# Выводим информацию о подключении (без пароля) для отладки
db_info = DATABASE_URL.split(":")
print(f"Connecting to database: {db_info[0]}://{db_info[1].split('@')[0].split(':')[0]}@{db_info[1].split('@')[1]}")

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