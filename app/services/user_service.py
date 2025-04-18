from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.models import User
from app.schemas.post_schemas import UserCreate, UserUpdate, UserUpdateProfile, UserUpdateAvatar
from fastapi import UploadFile, HTTPException
from app.utils.image_handler import ImageHandler
import logging

logger = logging.getLogger("app")

class UserService:
    @staticmethod
    async def create_user(db: Session, user_data: UserCreate):
        try:
            # Проверяем, существует ли пользователь с таким логином
            existing_user = db.query(User).filter(User.login == user_data.login).first()
            if existing_user:
                raise ValueError(f"Пользователь с логином {user_data.login} уже существует")
            
            # Получаем максимальное значение user_id и прибавляем 1
            max_id = db.query(func.max(User.user_id)).scalar() or 0
            next_id = max_id + 1
            
            # Обрабатываем аватар, если он предоставлен
            image_link = None
            if user_data.image:
                # Сохраняем изображение и получаем путь к нему
                success, file_path, error_message = ImageHandler.save_image(user_data.image, prefix="avatar_", directory="avatars")
                if not success:
                    logger.error(f"Ошибка при сохранении аватара: {error_message}")
                    raise HTTPException(status_code=400, detail=error_message)
                
                # Сохраняем ссылку на аватар
                image_link = file_path
            
            # Создаем пользователя
            db_user = User(
                user_id=next_id,
                login=user_data.login,
                name=user_data.name,
                password=user_data.password,
                type_id=user_data.type_id,
                image_link=image_link,
                description=user_data.description,
                rating=user_data.rating
            )
            
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
            logger.info(f"Created user with ID: {db_user.user_id}")
            return db_user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    @staticmethod
    async def update_user(db: Session, user_id: int, user_data: UserUpdate):
        try:
            db_user = db.query(User).filter(User.user_id == user_id).first()
            if not db_user:
                return None
            
            # Обрабатываем аватар, если он предоставлен
            if user_data.image:
                # Если у пользователя уже есть аватар, удаляем его
                if db_user.image_link and db_user.image_link.startswith("/uploads/avatars/"):
                    ImageHandler.delete_image(db_user.image_link)
                
                # Сохраняем новое изображение и получаем путь к нему
                success, file_path, error_message = ImageHandler.save_image(user_data.image, prefix="avatar_", directory="avatars")
                if not success:
                    logger.error(f"Ошибка при сохранении аватара: {error_message}")
                    raise HTTPException(status_code=400, detail=error_message)
                
                # Обновляем ссылку на аватар
                db_user.image_link = file_path
            
            # Обновляем остальные поля пользователя
            if user_data.name is not None:
                db_user.name = user_data.name
            if user_data.description is not None:
                db_user.description = user_data.description
            if user_data.rating is not None:
                db_user.rating = user_data.rating
            
            db.commit()
            db.refresh(db_user)
            logger.info(f"Updated user ID: {user_id}")
            return db_user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_user(db: Session, user_id: int):
        return db.query(User).filter(User.user_id == user_id).first()
    
    @staticmethod
    def delete_user(db: Session, user_id: int):
        try:
            db_user = db.query(User).filter(User.user_id == user_id).first()
            if db_user:
                # Удаляем аватар, если он существует
                if db_user.image_link and db_user.image_link.startswith("/uploads/avatars/"):
                    ImageHandler.delete_image(db_user.image_link)
                
                # Удаляем пользователя
                db.delete(db_user)
                db.commit()
                logger.info(f"Deleted user ID: {user_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise

    @staticmethod
    async def update_user_profile(db: Session, user_id: int, user_data: UserUpdateProfile):
        """
        Обновляет основную информацию о пользователе.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
            user_data (UserUpdateProfile): Данные для обновления
            
        Returns:
            User: Обновленный пользователь
        """
        try:
            db_user = db.query(User).filter(User.user_id == user_id).first()
            if not db_user:
                return None
            
            # Обновляем поля пользователя
            if user_data.name is not None:
                db_user.name = user_data.name
            if user_data.description is not None:
                db_user.description = user_data.description
            if user_data.rating is not None:
                db_user.rating = user_data.rating
            
            db.commit()
            db.refresh(db_user)
            logger.info(f"Updated user profile ID: {user_id}")
            return db_user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user profile {user_id}: {str(e)}")
            raise

    @staticmethod
    async def update_user_avatar(db: Session, user_id: int, user_data: UserUpdateAvatar):
        """
        Обновляет аватар пользователя.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
            user_data (UserUpdateAvatar): Новый аватар
            
        Returns:
            User: Обновленный пользователь
        """
        try:
            db_user = db.query(User).filter(User.user_id == user_id).first()
            if not db_user:
                return None
            
            # Если у пользователя уже есть аватар, удаляем его
            if db_user.image_link and db_user.image_link.startswith("/uploads/avatars/"):
                ImageHandler.delete_image(db_user.image_link)
            
            # Сохраняем новое изображение и получаем путь к нему
            success, file_path, error_message = ImageHandler.save_image(
                user_data.image, 
                prefix="avatar_", 
                directory="avatars"
            )
            if not success:
                logger.error(f"Ошибка при сохранении аватара: {error_message}")
                raise HTTPException(status_code=400, detail=error_message)
            
            # Обновляем ссылку на аватар
            db_user.image_link = file_path
            
            db.commit()
            db.refresh(db_user)
            logger.info(f"Updated user avatar ID: {user_id}")
            return db_user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user avatar {user_id}: {str(e)}")
            raise 