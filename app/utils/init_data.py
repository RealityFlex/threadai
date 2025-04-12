from sqlalchemy.orm import Session
from app.models.models import PostType, TagType, ProfileType, EducationType
import logging

logger = logging.getLogger("app")

def initialize_db(db: Session):
    """
    Инициализирует базу данных необходимыми начальными данными.
    
    Args:
        db (Session): Сессия SQLAlchemy
    """
    try:
        # Инициализация типов постов
        init_post_types(db)
        
        # Инициализация типов тегов
        init_tag_types(db)
        
        # Инициализация типов профилей
        init_profile_types(db)
        
        # Инициализация типов образования
        init_education_types(db)
        
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        db.rollback()
        raise

def init_post_types(db: Session):
    """Инициализация типов постов"""
    # Проверяем, есть ли уже записи
    count = db.query(PostType).count()
    if count > 0:
        return
    
    post_types = [
        PostType(post_type_id=1, name="Пост"),
        PostType(post_type_id=2, name="Комментарий"),
        PostType(post_type_id=3, name="Репост")
    ]
    db.add_all(post_types)
    db.commit()
    logger.info(f"Добавлено {len(post_types)} типов постов")

def init_tag_types(db: Session):
    """Инициализация типов тегов"""
    # Проверяем, есть ли уже записи
    count = db.query(TagType).count()
    if count > 0:
        return
    
    tag_types = [
        TagType(tag_type_id=1, name="Тема"),
        TagType(tag_type_id=2, name="Навык"),
        TagType(tag_type_id=3, name="Предмет")
    ]
    db.add_all(tag_types)
    db.commit()
    logger.info(f"Добавлено {len(tag_types)} типов тегов")

def init_profile_types(db: Session):
    """Инициализация типов профилей"""
    # Проверяем, есть ли уже записи
    count = db.query(ProfileType).count()
    if count > 0:
        return
    
    profile_types = [
        ProfileType(type_id=1, name="Студент"),
        ProfileType(type_id=2, name="Преподаватель"),
        ProfileType(type_id=3, name="Администратор")
    ]
    db.add_all(profile_types)
    db.commit()
    logger.info(f"Добавлено {len(profile_types)} типов профилей")

def init_education_types(db: Session):
    """Инициализация типов образования"""
    # Проверяем, есть ли уже записи
    count = db.query(EducationType).count()
    if count > 0:
        return
    
    education_types = [
        EducationType(education_type_id=1, name="Бакалавриат"),
        EducationType(education_type_id=2, name="Магистратура"),
        EducationType(education_type_id=3, name="Специалитет"),
        EducationType(education_type_id=4, name="Аспирантура")
    ]
    db.add_all(education_types)
    db.commit()
    logger.info(f"Добавлено {len(education_types)} типов образования") 