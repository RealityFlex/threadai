from sqlalchemy.orm import Session
from app.models.models import User
import logging
import hashlib

logger = logging.getLogger("app")

def create_test_user(db: Session):
    """
    Создает тестового пользователя, если он не существует
    
    Args:
        db (Session): Сессия SQLAlchemy
    
    Returns:
        User: Созданный или существующий тестовый пользователь
    """
    try:
        # Проверяем, существует ли уже тестовый пользователь
        test_user = db.query(User).filter(User.login == "test_user").first()
        
        if test_user:
            logger.info(f"Тестовый пользователь уже существует (ID: {test_user.user_id})")
            return test_user
        
        # Вычисляем максимальный ID пользователя и прибавляем 1
        max_id = db.query(User.user_id).order_by(User.user_id.desc()).first()
        new_id = 1 if max_id is None else max_id[0] + 1
        
        # Создаем простой хеш для пароля
        hashed_password = hashlib.sha256("test_password".encode()).hexdigest()
        
        # Создаем нового пользователя
        new_user = User(
            user_id=new_id,
            login="test_user",
            password=hashed_password,
            type_id=1,  # Тип "Студент"
            name="Тестовый Пользователь",
            description="Тестовый аккаунт для разработки",
            rating=5.0
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"Создан тестовый пользователь (ID: {new_user.user_id})")
        return new_user
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании тестового пользователя: {str(e)}")
        raise 