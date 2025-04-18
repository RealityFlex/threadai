import os
import uuid
import hashlib
import shutil
from datetime import datetime
from typing import Optional, Tuple
from fastapi import UploadFile
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

class ImageHandler:
    """
    Класс для обработки и сохранения загруженных изображений.
    Файлы сохраняются с зашифрованным именем для безопасности.
    """
    
    UPLOAD_DIR = "uploads"
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    @classmethod
    def save_image(cls, file: UploadFile, prefix: str = "", directory: str = "images") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Сохраняет загруженное изображение в папку с зашифрованным именем.
        
        Args:
            file (UploadFile): Загруженный файл
            prefix (str): Префикс для названия файла (например, 'post_', 'user_')
            directory (str): Поддиректория для сохранения файла (например, 'images', 'avatars')
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: 
                - Успешность операции
                - Путь к файлу для хранения в БД (относительный)
                - Сообщение об ошибке в случае неудачи
        """
        try:
            # Проверяем размер файла
            file_size = 0
            file.file.seek(0, 2)  # Перемещаемся в конец файла
            file_size = file.file.tell()  # Получаем размер
            file.file.seek(0)  # Возвращаемся в начало
            
            if file_size > cls.MAX_FILE_SIZE:
                return False, None, f"Файл слишком большой. Максимальный размер: {cls.MAX_FILE_SIZE / (1024 * 1024)}MB"
            
            # Получаем расширение файла и проверяем его
            _, ext = os.path.splitext(file.filename)
            ext = ext.lower()
            
            if ext not in cls.ALLOWED_EXTENSIONS:
                return False, None, f"Недопустимое расширение файла. Разрешены: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            
            # Генерируем уникальное зашифрованное имя файла
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_id = str(uuid.uuid4())
            
            # Создаем хеш на основе имени файла, времени и уникального ID
            hash_input = f"{file.filename}{timestamp}{unique_id}".encode('utf-8')
            hashed_name = hashlib.sha256(hash_input).hexdigest()[:16]  # Берем первые 16 символов хеша
            
            # Формируем окончательное имя файла
            filename = f"{prefix}{timestamp}_{hashed_name}{ext}"
            
            # Формируем путь к директории
            upload_dir = os.path.join(cls.UPLOAD_DIR, directory)
            
            # Убедимся, что директория существует
            os.makedirs(upload_dir, exist_ok=True)
            
            # Полный путь для сохранения файла
            file_path = os.path.join(upload_dir, filename)
            
            # Сохраняем файл
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Формируем относительный путь для сохранения в БД
            relative_path = f"/uploads/{directory}/{filename}"
            
            logger.info(f"Изображение сохранено: {file_path}")
            return True, relative_path, None
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении изображения: {str(e)}")
            return False, None, f"Ошибка при сохранении изображения: {str(e)}"
    
    @classmethod
    def delete_image(cls, file_path: str) -> bool:
        """
        Удаляет изображение по указанному пути.
        
        Args:
            file_path (str): Путь к файлу (относительный, начинающийся с '/uploads/images/')
            
        Returns:
            bool: True если удаление успешно, False в противном случае
        """
        try:
            # Проверяем, начинается ли путь с /uploads/images/
            if not file_path.startswith("/uploads/images/"):
                logger.error(f"Попытка удалить файл вне директории изображений: {file_path}")
                return False
            
            # Получаем имя файла
            filename = os.path.basename(file_path)
            
            # Полный путь к файлу
            full_path = os.path.join(cls.UPLOAD_DIR, filename)
            
            # Проверяем существование файла
            if not os.path.exists(full_path):
                logger.warning(f"Файл не найден: {full_path}")
                return False
            
            # Удаляем файл
            os.remove(full_path)
            logger.info(f"Изображение удалено: {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении изображения: {str(e)}")
            return False 