from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union, ForwardRef
from datetime import datetime, date
from fastapi import UploadFile

# Базовые схемы
class TagTypeBase(BaseModel):
    type_id: int
    name: str

    class Config:
        orm_mode = True

class TagBase(BaseModel):
    name: str
    tag_type_id: int
    tag_type: Optional[TagTypeBase] = None

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    tag_id: int

    class Config:
        orm_mode = True

# Схемы для постов
class PostBase(BaseModel):
    content: str
    child_id: Optional[int] = None
    media_link: Optional[str] = None
    post_type_id: int = Field(..., ge=1, description="ID типа поста (1-Пост, 2-Комментарий, 3-Репост)")
    
    @validator('post_type_id')
    def validate_post_type(cls, v):
        if v not in [1, 2, 3]:
            raise ValueError("Тип поста должен быть одним из: 1 (Пост), 2 (Комментарий), 3 (Репост)")
        return v

class PostCreate(PostBase):
    user_id: int = Field(..., ge=1, description="ID пользователя")

class PostUpdate(BaseModel):
    content: Optional[str] = None
    media_link: Optional[str] = None

class Post(PostBase):
    post_id: int
    user_id: int
    creation_date: datetime
    views_count: int

    class Config:
        orm_mode = True

# Схемы для лайков
class LikeBase(BaseModel):
    post_id: int = Field(..., ge=1)
    user_id: int = Field(..., ge=1)

class LikeCreate(LikeBase):
    pass

class Like(LikeBase):
    like_id: int

    class Config:
        orm_mode = True

# Схемы для комментариев (частный случай поста)
class CommentBase(BaseModel):
    content: str
    child_id: int = Field(..., ge=1, description="ID родительского поста или комментария")
    media_link: Optional[str] = None
    post_type_id: int = Field(2, description="ID типа поста (комментарий)")  # Всегда 2 для комментариев

class CommentCreate(CommentBase):
    user_id: int = Field(..., ge=1, description="ID пользователя")

class Comment(CommentBase):
    post_id: int
    user_id: int
    creation_date: datetime
    views_count: int

    class Config:
        orm_mode = True

# Рекурсивная модель для комментариев с их подкомментариями
CommentWithRepliesRef = ForwardRef("CommentWithReplies")

class CommentWithReplies(Comment):
    replies: List[CommentWithRepliesRef] = []

    class Config:
        orm_mode = True

# Обновляем PostDetail для включения комментариев и информации о пользователе
class PostDetail(Post):
    likes_count: int
    tags: List[Tag] = []
    comments: List[CommentWithReplies] = []
    user_name: str
    user_image: Optional[str] = None

    class Config:
        orm_mode = True

# Схемы для пользователей
class ProfileTypeBase(BaseModel):
    type_id: int
    name: str
    
    class Config:
        orm_mode = True

class UserBase(BaseModel):
    login: str
    name: str
    type_id: int
    image_link: Optional[str] = None
    description: Optional[str] = None
    rating: float

class UserCreate(UserBase):
    password: str
    image: Optional[bytes] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None
    image: Optional[bytes] = None

class UserDetail(UserBase):
    user_id: int
    tags: List[Tag] = []
    post_count: int = 0
    likes_count: int = 0
    
    class Config:
        orm_mode = True

class UserUpdateProfile(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None

class UserUpdateAvatar(BaseModel):
    image: bytes

# Разрешаем форвард-референс
CommentWithReplies.update_forward_refs() 