from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.services.post_service import PostService
from app.schemas.post_schemas import (
    Post, PostCreate, PostUpdate, PostDetail, 
    Like, LikeCreate, Comment, CommentCreate, Tag,
    UserDetail, UserCreate, UserUpdate
)
from app.utils.init_data import initialize_db
from app.utils.create_test_user import create_test_user
from app.models.models import User, PostType
from app.services.user_service import UserService

router = APIRouter()

# Маршрут для инициализации БД
@router.post("/system/init-db", tags=["Система"])
def init_db(db: Session = Depends(get_db)):
    """
    Инициализация базы данных начальными значениями.
    
    Добавляет необходимые справочные данные:
    - Типы постов
    - Типы тегов
    - Типы профилей
    - Типы образования
    """
    try:
        initialize_db(db)
        return {"status": "success", "message": "База данных успешно инициализирована"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при инициализации базы данных: {str(e)}"
        )

# Маршрут для создания тестового пользователя
@router.post("/system/create-test-user", tags=["Система"])
def add_test_user(db: Session = Depends(get_db)):
    """
    Создает тестового пользователя для разработки и тестирования.
    
    Если тестовый пользователь уже существует, вернет существующего.
    """
    try:
        user = create_test_user(db)
        return {
            "status": "success", 
            "message": "Тестовый пользователь создан или уже существует",
            "user_id": user.user_id,
            "login": user.login
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании тестового пользователя: {str(e)}"
        )

# Получение справочников
@router.get("/system/post-types", tags=["Система"])
def get_post_types(db: Session = Depends(get_db)):
    """
    Получение списка доступных типов постов.
    
    Полезно для выбора правильного post_type_id при создании поста.
    """
    post_types = db.query(PostType).all()
    return [{"id": pt.post_type_id, "name": pt.name} for pt in post_types]

@router.get("/system/users", tags=["Система"])
def get_users(db: Session = Depends(get_db)):
    """
    Получение списка пользователей.
    
    Полезно для выбора правильного user_id при создании поста.
    """
    users = db.query(User).all()
    return [{"id": u.user_id, "login": u.login, "name": u.name} for u in users]

# Маршруты для постов
@router.post("/posts/", response_model=Post, tags=["Посты"])
async def create_post(
    content: str = Form(...),
    user_id: int = Form(...),
    child_id: Optional[int] = Form(None),
    post_type_id: int = Form(...),
    media_link: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db)
):
    """
    Создать новый пост.
    
    Пост может быть основным или ответом на существующий пост (комментарием).
    К посту можно прикрепить изображение или указать ссылку на медиа-контент.
    
    Если child_id не указан или передан как пустая строка, он будет установлен как None.
    """
    try:
        # Преобразуем child_id к правильному типу (None, если передана пустая строка)
        processed_child_id = None
        if child_id and str(child_id).strip():
            try:
                processed_child_id = int(child_id)
            except (ValueError, TypeError):
                processed_child_id = None
        
        # Создаем объект PostCreate из данных формы
        post_data = PostCreate(
            content=content,
            user_id=user_id,
            child_id=processed_child_id,
            post_type_id=post_type_id,
            media_link=media_link
        )
        
        # Создаем пост с изображением, если оно предоставлено
        post = await PostService.create_post(db, post_data=post_data, image=image)
        return post
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании поста: {str(e)}"
        )

@router.get("/posts/", response_model=List[PostDetail], tags=["Посты"])
def read_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получить список постов.
    
    Возвращает пагинированный список постов с информацией о пользователе, лайках и комментариях.
    """
    posts = PostService.get_posts(db, skip=skip, limit=limit)
    return posts

@router.get("/posts/{post_id}", response_model=PostDetail, tags=["Посты"])
def read_post(post_id: int, db: Session = Depends(get_db)):
    """
    Получить детальную информацию о посте.
    
    Возвращает пост с дополнительной информацией, такой как количество лайков и теги.
    При просмотре увеличивается счетчик просмотров.
    """
    post = PostService.get_post_with_details(db, post_id=post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return post

@router.put("/posts/{post_id}", response_model=Post, tags=["Посты"])
async def update_post(
    post_id: int,
    content: Optional[str] = Form(None),
    media_link: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db)
):
    """
    Обновить существующий пост.
    
    Можно обновить содержание поста и/или медиа-контент.
    При загрузке нового изображения, старое изображение будет удалено.
    """
    try:
        # Создаем объект PostUpdate из данных формы
        post_data = PostUpdate(
            content=content,
            media_link=media_link
        )
        
        # Обновляем пост с изображением, если оно предоставлено
        post = await PostService.update_post(db, post_id=post_id, post_data=post_data, image=image)
        if not post:
            raise HTTPException(status_code=404, detail=f"Пост с ID {post_id} не найден")
        return post
    except HTTPException:
        # Проксируем HTTPException из сервиса
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении поста: {str(e)}"
        )

@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Посты"])
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """
    Удалить пост.
    
    Удаляет пост и все связанные с ним данные (лайки, теги).
    """
    success = PostService.delete_post(db, post_id=post_id)
    if not success:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return {"detail": "Пост успешно удален"}

# Маршруты для комментариев
@router.post("/comments/", response_model=Comment, status_code=status.HTTP_201_CREATED, tags=["Комментарии"])
async def create_comment(
    content: str = Form(...),
    user_id: int = Form(...),
    child_id: int = Form(...),
    media_link: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db)
):
    """
    Создать комментарий.
    
    Комментарий - это особый тип поста, который имеет родительский пост или комментарий.
    
    - post_type_id всегда равен 2 (для комментария)
    - child_id должен указывать на существующий пост или комментарий
    - user_id должен соответствовать существующему пользователю
    - Может содержать изображение
    """
    try:
        # Создаем объект CommentCreate из данных формы
        comment = CommentCreate(
            content=content,
            user_id=user_id,
            child_id=child_id,
            post_type_id=2,
            media_link=media_link
        )
        
        # Создаем комментарий с изображением, если оно предоставлено
        post = await PostService.create_post(db=db, post_data=comment, image=image)
        return post
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.get("/posts/{post_id}/comments/", response_model=List[Comment], tags=["Комментарии"])
def read_comments(post_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получить комментарии к посту.
    
    Возвращает пагинированный список комментариев к указанному посту.
    """
    comments = PostService.get_comments(db, post_id=post_id, skip=skip, limit=limit)
    return comments

# Маршруты для лайков
@router.post("/likes/", response_model=Like, status_code=status.HTTP_201_CREATED, tags=["Лайки"])
def create_like(like: LikeCreate, db: Session = Depends(get_db)):
    """
    Поставить лайк.
    
    Добавляет лайк от пользователя к посту. Если лайк уже существует, 
    возвращает существующий лайк.
    """
    try:
        return PostService.like_post(db=db, like_data=like)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

@router.delete("/posts/{post_id}/likes/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Лайки"])
def delete_like(post_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Убрать лайк.
    
    Удаляет лайк пользователя с указанного поста.
    """
    success = PostService.unlike_post(db, post_id=post_id, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Лайк не найден")
    return {"detail": "Лайк успешно удален"}

# Маршруты для рекомендаций и тегов пользователя
@router.get("/users/{user_id}/recommended-posts", response_model=List[PostDetail], tags=["Рекомендации"])
def get_recommended_posts(user_id: int, skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """
    Получить рекомендованные посты для пользователя.
    
    Возвращает список постов, наиболее соответствующих интересам пользователя,
    основываясь на его тегах и лайках. Учитывает также популярность постов
    и их новизну.
    """
    try:
        # Проверяем существование пользователя
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
        
        # Получаем рекомендованные посты
        posts = PostService.get_recommended_posts(db, user_id=user_id, skip=skip, limit=limit)
        return posts
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении рекомендаций: {str(e)}"
        )

@router.get("/users/{user_id}/tags", response_model=List[Tag], tags=["Пользователи"])
def get_user_tags(user_id: int, db: Session = Depends(get_db)):
    """
    Получить теги пользователя.
    
    Возвращает список тегов, которые соответствуют интересам пользователя.
    Эти теги формируются на основе лайков пользователя и определяют 
    его предпочтения для рекомендательной системы.
    """
    try:
        # Проверяем существование пользователя
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
        
        # Получаем теги пользователя
        tags = PostService.get_user_tags(db, user_id=user_id)
        return tags
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении тегов пользователя: {str(e)}"
        )

@router.get("/users/{user_id}", response_model=UserDetail, tags=["Пользователи"])
def get_user_details(user_id: int, db: Session = Depends(get_db)):
    """
    Получить подробную информацию о пользователе.
    
    Возвращает детальную информацию о пользователе, включая его облако тегов,
    статистику постов и лайков, и другие данные профиля.
    """
    try:
        # Получаем детальную информацию о пользователе
        user_details = PostService.get_user_details(db, user_id=user_id)
        if not user_details:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
        
        return user_details
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении информации о пользователе: {str(e)}"
        )

# Маршруты для пользователей
@router.post("/users/", response_model=UserDetail, status_code=status.HTTP_201_CREATED, tags=["Пользователи"])
async def create_user(
    login: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    type_id: int = Form(...),
    description: Optional[str] = Form(None),
    rating: float = Form(0.0),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Создать нового пользователя.
    
    Можно загрузить аватар пользователя.
    """
    try:
        user_data = UserCreate(
            login=login,
            name=name,
            password=password,
            type_id=type_id,
            description=description,
            rating=rating,
            image=image
        )
        user = await UserService.create_user(db, user_data=user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании пользователя: {str(e)}"
        )

@router.put("/users/{user_id}", response_model=UserDetail, tags=["Пользователи"])
async def update_user(
    user_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    rating: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о пользователе.
    
    Можно обновить имя, описание, рейтинг и аватар.
    При загрузке нового аватара, старый будет удален.
    """
    try:
        user_data = UserUpdate(
            name=name,
            description=description,
            rating=rating,
            image=image
        )
        user = await UserService.update_user(db, user_id=user_id, user_data=user_data)
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {user_id} не найден")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении пользователя: {str(e)}"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Пользователи"])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Удалить пользователя.
    
    Удаляет пользователя и его аватар, если он существует.
    """
    success = UserService.delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"detail": "Пользователь успешно удален"} 