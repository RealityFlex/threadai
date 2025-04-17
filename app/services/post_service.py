from sqlalchemy.orm import Session
from sqlalchemy import func, text, desc, and_, or_, distinct
from app.models.models import Post, Like, TagForPost, Tag, User, PostType, TagForUser, ProfileType
from app.schemas.post_schemas import PostCreate, PostUpdate, LikeCreate, CommentWithReplies
import sys
import os
import logging
from collections import Counter
from datetime import datetime, timedelta
from fastapi import UploadFile, HTTPException
from app.utils.image_handler import ImageHandler

# Добавляем корневую директорию проекта в sys.path для импорта tokens.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from tokens import extract_topic_tokens

# Получаем логгер
logger = logging.getLogger("app")

class PostService:
    @staticmethod
    async def create_post(db: Session, post_data: PostCreate, image: UploadFile = None):
        try:
            # Проверяем существование пользователя
            user = db.query(User).filter(User.user_id == post_data.user_id).first()
            if not user:
                logger.error(f"Попытка создать пост для несуществующего пользователя ID={post_data.user_id}")
                raise ValueError(f"Пользователь с ID {post_data.user_id} не существует")
            
            # Проверяем существование типа поста
            post_type = db.query(PostType).filter(PostType.post_type_id == post_data.post_type_id).first()
            if not post_type:
                logger.error(f"Попытка создать пост с несуществующим типом ID={post_data.post_type_id}")
                raise ValueError(f"Тип поста с ID {post_data.post_type_id} не существует. Доступные типы: 1 (Пост), 2 (Комментарий), 3 (Репост)")
            
            # Если указан child_id, проверяем его существование
            if post_data.child_id is not None:
                parent_post = db.query(Post).filter(Post.post_id == post_data.child_id).first()
                if not parent_post:
                    logger.error(f"Попытка создать комментарий к несуществующему посту ID={post_data.child_id}")
                    raise ValueError(f"Родительский пост с ID {post_data.child_id} не существует")
            
            # Обрабатываем изображение, если оно предоставлено
            media_link = post_data.media_link
            if image:
                # Сохраняем изображение и получаем путь к нему
                success, file_path, error_message = ImageHandler.save_image(image, prefix="post_")
                if not success:
                    logger.error(f"Ошибка при сохранении изображения для поста: {error_message}")
                    raise HTTPException(status_code=400, detail=error_message)
                
                # Заменяем ссылку на медиа-контент путем к сохраненному изображению
                media_link = file_path
            
            # Получаем максимальное значение post_id и прибавляем 1
            max_id = db.query(func.max(Post.post_id)).scalar() or 0
            next_id = max_id + 1
            
            # Создаем пост с явным указанием ID
            db_post = Post(
                post_id=next_id,
                content=post_data.content,
                child_id=post_data.child_id,
                user_id=post_data.user_id,
                media_link=media_link,
                post_type_id=post_data.post_type_id
            )
            
            db.add(db_post)
            db.commit()
            db.refresh(db_post)
            
            # Логируем успешное создание
            logger.info(f"Created post with ID: {db_post.post_id}")
            
            # Генерируем тэги для поста
            tokens = extract_topic_tokens(post_data.content)
            if tokens:
                # Создаем или получаем существующие тэги
                for token in tokens:
                    # Ищем тэг в БД или создаем новый
                    tag = db.query(Tag).filter(Tag.name == token).first()
                    if not tag:
                        # По умолчанию используем тип 1 (его нужно создать в БД)
                        # Получаем максимальное значение tag_id и прибавляем 1
                        max_tag_id = db.query(func.max(Tag.tag_id)).scalar() or 0
                        next_tag_id = max_tag_id + 1
                        
                        tag = Tag(tag_id=next_tag_id, name=token, tag_type_id=1)
                        db.add(tag)
                        db.commit()
                        db.refresh(tag)
                    
                    # Проверяем существование связи между постом и тегом
                    existing_tag_for_post = db.query(TagForPost).filter(
                        TagForPost.post_id == db_post.post_id,
                        TagForPost.tag_id == tag.tag_id
                    ).first()
                    
                    # Если связь уже существует, пропускаем
                    if existing_tag_for_post:
                        continue
                    
                    # Получаем максимальное значение id для TagForPost из отдельного запроса
                    # и сразу фиксируем транзакцию, чтобы получить актуальное значение
                    max_tag_post_id = db.query(func.max(TagForPost.id)).scalar() or 0
                    next_tag_post_id = max_tag_post_id + 1
                    
                    # Связываем тэг с постом
                    tag_for_post = TagForPost(
                        id=next_tag_post_id,
                        post_id=db_post.post_id, 
                        tag_id=tag.tag_id
                    )
                    db.add(tag_for_post)
                    # Фиксируем каждую связь отдельно, чтобы избежать конфликтов ID
                    db.commit()
                
                logger.info(f"Added tags to post ID: {db_post.post_id}")
            
            return db_post
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating post: {str(e)}")
            raise
    
    @staticmethod
    def get_post(db: Session, post_id: int):
        return db.query(Post).filter(Post.post_id == post_id).first()
    
    @staticmethod
    def get_posts(db: Session, skip: int = 0, limit: int = 100):
        """
        Получает список постов с информацией о пользователе, лайках и комментариях.
        """
        try:
            # Получаем базовый список постов с информацией о пользователе
            posts = db.query(Post, User).join(User).filter(
                Post.child_id.is_(None),  # Только основные посты
                Post.post_type_id == 1    # Только посты (не комментарии)
            ).order_by(desc(Post.creation_date)).offset(skip).limit(limit).all()
            
            # Для каждого поста получаем детальную информацию
            posts_with_details = []
            for post, user in posts:
                # Получаем количество лайков
                likes_count = db.query(func.count(Like.like_id)).filter(Like.post_id == post.post_id).scalar()
                
                # Получаем теги поста
                tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post.post_id).all()
                
                # Получаем комментарии первого уровня
                comments = db.query(Post).filter(Post.child_id == post.post_id).order_by(Post.creation_date).all()
                
                # Формируем структуру комментариев с вложенными ответами
                def get_comment_replies(comment_id):
                    replies = db.query(Post).filter(Post.child_id == comment_id).order_by(Post.creation_date).all()
                    replies_with_nested = []
                    
                    for reply in replies:
                        sub_replies = get_comment_replies(reply.post_id)
                        reply_dict = {
                            "post_id": reply.post_id,
                            "content": reply.content,
                            "child_id": reply.child_id,
                            "user_id": reply.user_id,
                            "media_link": reply.media_link,
                            "creation_date": reply.creation_date,
                            "views_count": reply.views_count,
                            "post_type_id": reply.post_type_id,
                            "replies": sub_replies
                        }
                        replies_with_nested.append(reply_dict)
                    
                    return replies_with_nested
                
                # Формируем список комментариев с вложенными ответами
                comments_with_replies = []
                for comment in comments:
                    replies = get_comment_replies(comment.post_id)
                    comment_dict = {
                        "post_id": comment.post_id,
                        "content": comment.content,
                        "child_id": comment.child_id,
                        "user_id": comment.user_id,
                        "media_link": comment.media_link,
                        "creation_date": comment.creation_date,
                        "views_count": comment.views_count,
                        "post_type_id": comment.post_type_id,
                        "replies": replies
                    }
                    comments_with_replies.append(comment_dict)
                
                # Формируем детальную информацию о посте
                post_dict = {
                    "post_id": post.post_id,
                    "content": post.content,
                    "child_id": post.child_id,
                    "user_id": post.user_id,
                    "user_name": user.name,
                    "user_image": user.image_link,
                    "media_link": post.media_link,
                    "creation_date": post.creation_date,
                    "views_count": post.views_count,
                    "post_type_id": post.post_type_id,
                    "likes_count": likes_count,
                    "tags": tags,
                    "comments": comments_with_replies
                }
                
                posts_with_details.append(post_dict)
            
            return posts_with_details
            
        except Exception as e:
            logger.error(f"Error getting posts: {str(e)}")
            raise
    
    @staticmethod
    def get_comments(db: Session, post_id: int, skip: int = 0, limit: int = 100):
        return db.query(Post).filter(Post.child_id == post_id).order_by(Post.creation_date).offset(skip).limit(limit).all()
    
    @staticmethod
    async def update_post(db: Session, post_id: int, post_data: PostUpdate, image: UploadFile = None):
        try:
            db_post = db.query(Post).filter(Post.post_id == post_id).first()
            if not db_post:
                return None
            
            # Обрабатываем изображение, если оно предоставлено
            if image:
                # Если у поста уже есть изображение, удаляем его
                if db_post.media_link and db_post.media_link.startswith("/uploads/images/"):
                    ImageHandler.delete_image(db_post.media_link)
                
                # Сохраняем новое изображение и получаем путь к нему
                success, file_path, error_message = ImageHandler.save_image(image, prefix="post_")
                if not success:
                    logger.error(f"Ошибка при сохранении изображения для поста {post_id}: {error_message}")
                    raise HTTPException(status_code=400, detail=error_message)
                
                # Обновляем ссылку на медиа-контент
                db_post.media_link = file_path
            # Если передали новую ссылку на медиа, обновляем ее
            elif post_data.media_link is not None:
                # Если у поста уже есть изображение в нашей системе и его заменяют на внешнюю ссылку, удаляем старое изображение
                if db_post.media_link and db_post.media_link.startswith("/uploads/images/") and not post_data.media_link.startswith("/uploads/images/"):
                    ImageHandler.delete_image(db_post.media_link)
                db_post.media_link = post_data.media_link
            
            # Обновляем остальные поля поста
            if post_data.content is not None:
                db_post.content = post_data.content
                # Обновляем теги поста при изменении содержания
                updated_tokens = extract_topic_tokens(post_data.content)
                if updated_tokens:
                    # Удаляем старые теги
                    db.query(TagForPost).filter(TagForPost.post_id == post_id).delete()
                    db.commit()
                    
                    # Создаем новые теги
                    for token in updated_tokens:
                        # Ищем тэг в БД или создаем новый
                        tag = db.query(Tag).filter(Tag.name == token).first()
                        if not tag:
                            # По умолчанию используем тип 1
                            max_tag_id = db.query(func.max(Tag.tag_id)).scalar() or 0
                            next_tag_id = max_tag_id + 1
                            
                            tag = Tag(tag_id=next_tag_id, name=token, tag_type_id=1)
                            db.add(tag)
                            db.commit()
                            db.refresh(tag)
                        
                        # Проверяем существование связи между постом и тегом
                        existing_tag_for_post = db.query(TagForPost).filter(
                            TagForPost.post_id == post_id,
                            TagForPost.tag_id == tag.tag_id
                        ).first()
                        
                        # Если связь уже существует, пропускаем
                        if existing_tag_for_post:
                            continue
                            
                        # Получаем максимальное значение id для TagForPost
                        max_tag_post_id = db.query(func.max(TagForPost.id)).scalar() or 0
                        next_tag_post_id = max_tag_post_id + 1
                        
                        # Связываем тэг с постом
                        tag_for_post = TagForPost(
                            id=next_tag_post_id,
                            post_id=post_id, 
                            tag_id=tag.tag_id
                        )
                        db.add(tag_for_post)
                        db.commit()
            
            db.commit()
            db.refresh(db_post)
            logger.info(f"Updated post ID: {post_id}")
            return db_post
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating post {post_id}: {str(e)}")
            raise
    
    @staticmethod
    def delete_post(db: Session, post_id: int):
        try:
            db_post = db.query(Post).filter(Post.post_id == post_id).first()
            if db_post:
                # Удаляем изображение, если оно хранится в нашей системе
                if db_post.media_link and db_post.media_link.startswith("/uploads/images/"):
                    ImageHandler.delete_image(db_post.media_link)
                
                # Удаляем связанные данные
                db.query(Like).filter(Like.post_id == post_id).delete()
                db.query(TagForPost).filter(TagForPost.post_id == post_id).delete()
                
                # Удаляем пост
                db.delete(db_post)
                db.commit()
                logger.info(f"Deleted post ID: {post_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting post {post_id}: {str(e)}")
            raise
    
    @staticmethod
    def like_post(db: Session, like_data: LikeCreate):
        try:
            # Проверяем, существует ли уже лайк
            existing_like = db.query(Like).filter(
                Like.post_id == like_data.post_id,
                Like.user_id == like_data.user_id
            ).first()
            
            # Если лайк уже существует, возвращаем его
            if existing_like:
                return existing_like
            
            # Получаем максимальное значение like_id и прибавляем 1
            max_like_id = db.query(func.max(Like.like_id)).scalar() or 0
            next_like_id = max_like_id + 1
            
            # Создаем новый лайк
            db_like = Like(
                like_id=next_like_id,
                post_id=like_data.post_id,
                user_id=like_data.user_id
            )
            db.add(db_like)
            db.commit()
            db.refresh(db_like)
            logger.info(f"User {like_data.user_id} liked post {like_data.post_id}")
            
            # Обновляем все теги пользователя после лайка
            try:
                # Обновляем теги пользователя на основе всех его лайков
                # Получаем все посты, которые лайкнул пользователь (включая только что добавленный)
                liked_posts = db.query(Post).join(Like).filter(Like.user_id == like_data.user_id).all()
                
                if liked_posts:
                    # Получаем теги из всех лайкнутых постов
                    post_tags = []
                    for post in liked_posts:
                        tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post.post_id).all()
                        post_tags.extend(tags)
                    
                    # Подсчитываем частоту тегов
                    tag_counter = Counter([tag.tag_id for tag in post_tags])
                    most_common_tags = tag_counter.most_common(10)  # Берем 10 самых популярных тегов
                    
                    # Очищаем текущие теги пользователя
                    db.query(TagForUser).filter(TagForUser.user_id == like_data.user_id).delete()
                    db.commit()
                    
                    # Добавляем новые теги
                    for tag_id, _ in most_common_tags:
                        # Получаем максимальное значение id для TagForUser и прибавляем 1
                        max_tag_user_id = db.query(func.max(TagForUser.id)).scalar() or 0
                        next_tag_user_id = max_tag_user_id + 1
                        
                        # Создаем новую связь между пользователем и тегом
                        tag_for_user = TagForUser(
                            id=next_tag_user_id,
                            user_id=like_data.user_id,
                            tag_id=tag_id
                        )
                        db.add(tag_for_user)
                        # Фиксируем каждое добавление тега отдельно
                        db.commit()
                    
                    logger.info(f"Updated all user tags for user ID: {like_data.user_id} after liking post ID: {like_data.post_id}")
            except Exception as e:
                logger.error(f"Error updating user tags after like: {str(e)}")
                # Не прерываем основной поток выполнения, если обновление тегов не удалось
                # Но откатываем транзакцию, чтобы не осталось незавершенных операций
                db.rollback()
            
            return db_like
        except Exception as e:
            db.rollback()
            logger.error(f"Error liking post {like_data.post_id} by user {like_data.user_id}: {str(e)}")
            raise
    
    @staticmethod
    def unlike_post(db: Session, post_id: int, user_id: int):
        try:
            db_like = db.query(Like).filter(
                Like.post_id == post_id,
                Like.user_id == user_id
            ).first()
            
            if db_like:
                db.delete(db_like)
                db.commit()
                logger.info(f"User {user_id} unliked post {post_id}")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error unliking post {post_id} by user {user_id}: {str(e)}")
            raise
    
    @staticmethod
    def get_post_with_details(db: Session, post_id: int):
        try:
            # Получаем пост со всеми связанными данными
            post = db.query(Post).filter(Post.post_id == post_id).first()
            
            if not post:
                return None
            
            # Получаем количество лайков
            likes_count = db.query(func.count(Like.like_id)).filter(Like.post_id == post_id).scalar()
            
            # Получаем теги поста
            tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post_id).all()
            
            # Получаем комментарии первого уровня для поста
            comments = db.query(Post).filter(Post.child_id == post_id).order_by(Post.creation_date).all()
            
            # Рекурсивно получаем древовидную структуру комментариев
            def get_comment_replies(comment_id):
                replies = db.query(Post).filter(Post.child_id == comment_id).order_by(Post.creation_date).all()
                replies_with_nested = []
                
                for reply in replies:
                    # Получаем подкомментарии для текущего комментария
                    sub_replies = get_comment_replies(reply.post_id)
                    
                    # Формируем структуру комментария с его подкомментариями
                    reply_dict = {
                        "post_id": reply.post_id,
                        "content": reply.content,
                        "child_id": reply.child_id,
                        "user_id": reply.user_id,
                        "media_link": reply.media_link,
                        "creation_date": reply.creation_date,
                        "views_count": reply.views_count,
                        "post_type_id": reply.post_type_id,
                        "replies": sub_replies
                    }
                    replies_with_nested.append(reply_dict)
                
                return replies_with_nested
            
            # Формируем список комментариев с вложенными ответами
            comments_with_replies = []
            for comment in comments:
                replies = get_comment_replies(comment.post_id)
                comment_dict = {
                    "post_id": comment.post_id,
                    "content": comment.content,
                    "child_id": comment.child_id,
                    "user_id": comment.user_id,
                    "media_link": comment.media_link,
                    "creation_date": comment.creation_date,
                    "views_count": comment.views_count,
                    "post_type_id": comment.post_type_id,
                    "replies": replies
                }
                comments_with_replies.append(comment_dict)
            
            # Увеличиваем счетчик просмотров
            post.views_count += 1
            db.commit()
            
            # Создаем копию объекта поста для добавления дополнительных полей
            post_dict = {
                "post_id": post.post_id,
                "content": post.content,
                "child_id": post.child_id,
                "user_id": post.user_id,
                "media_link": post.media_link,
                "creation_date": post.creation_date,
                "views_count": post.views_count,
                "post_type_id": post.post_type_id,
                "likes_count": likes_count,
                "tags": tags,
                "comments": comments_with_replies
            }
            
            return post_dict
        except Exception as e:
            db.rollback()
            logger.error(f"Error getting post details for ID {post_id}: {str(e)}")
            raise

    @staticmethod
    def get_user_tags(db: Session, user_id: int):
        """
        Получает список тегов пользователя.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
            
        Returns:
            list: Список тегов пользователя
        """
        try:
            # Получаем теги пользователя
            tags = db.query(Tag).join(TagForUser).filter(TagForUser.user_id == user_id).all()
            return tags
        except Exception as e:
            logger.error(f"Error getting user tags for user ID {user_id}: {str(e)}")
            raise

    @staticmethod
    def update_user_tags_from_likes(db: Session, user_id: int):
        """
        Обновляет теги пользователя на основе его лайков.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
        """
        try:
            # Проверяем существование пользователя
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.error(f"Attempt to update tags for non-existent user ID={user_id}")
                raise ValueError(f"User with ID {user_id} does not exist")
            
            # Получаем посты, которые лайкнул пользователь
            liked_posts = db.query(Post).join(Like).filter(Like.user_id == user_id).all()
            
            if not liked_posts:
                logger.info(f"User {user_id} has no liked posts")
                return
            
            # Получаем теги из лайкнутых постов
            post_tags = []
            for post in liked_posts:
                tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post.post_id).all()
                post_tags.extend(tags)
            
            # Подсчитываем частоту тегов
            tag_counter = Counter([tag.tag_id for tag in post_tags])
            most_common_tags = tag_counter.most_common(10)  # Берем 10 самых популярных тегов
            
            # Очищаем текущие теги пользователя
            db.query(TagForUser).filter(TagForUser.user_id == user_id).delete()
            db.commit()
            
            # Добавляем новые теги
            for tag_id, _ in most_common_tags:
                # Получаем максимальное значение id для TagForUser и прибавляем 1
                max_tag_user_id = db.query(func.max(TagForUser.id)).scalar() or 0
                next_tag_user_id = max_tag_user_id + 1
                
                # Создаем новую связь между пользователем и тегом
                tag_for_user = TagForUser(
                    id=next_tag_user_id,
                    user_id=user_id,
                    tag_id=tag_id
                )
                db.add(tag_for_user)
                # Фиксируем каждое добавление тега отдельно
                db.commit()
            
            logger.info(f"Updated tags for user ID: {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user tags: {str(e)}")
            raise

    @staticmethod
    def get_recommended_posts(db: Session, user_id: int, skip: int = 0, limit: int = 10):
        """
        Получает рекомендованные посты для пользователя с учетом его интересов и популярности постов.
        """
        try:
            # Получаем теги пользователя
            user_tags = db.query(Tag).join(TagForUser).filter(TagForUser.user_id == user_id).all()
            user_tag_ids = [tag.tag_id for tag in user_tags]
            
            # Получаем посты, которые пользователь уже лайкнул
            liked_posts = db.query(Like.post_id).filter(Like.user_id == user_id).all()
            liked_post_ids = [post_id for (post_id,) in liked_posts]
            
            # Получаем все посты с тегами и информацией о пользователе
            posts_query = db.query(Post, User).join(User).join(TagForPost).join(Tag).filter(
                Post.child_id.is_(None),  # Только основные посты
                Post.post_type_id == 1,   # Только посты (не комментарии)
                ~Post.post_id.in_(liked_post_ids)  # Исключаем посты, которые пользователь уже лайкнул
            )
            
            # Если у пользователя есть теги, добавляем фильтр по тегам
            if user_tag_ids:
                posts_query = posts_query.filter(Tag.tag_id.in_(user_tag_ids))
            
            # Получаем посты, упорядоченные по дате создания
            posts = posts_query.order_by(desc(Post.creation_date)).offset(skip).limit(limit).all()
            
            # Если постов с тегами пользователя недостаточно, добавляем популярные посты
            if len(posts) < limit:
                remaining_limit = limit - len(posts)
                popular_posts = db.query(Post, User).join(User).join(Like).filter(
                    Post.child_id.is_(None),
                    Post.post_type_id == 1,
                    ~Post.post_id.in_(liked_post_ids),
                    ~Post.post_id.in_([p[0].post_id for p in posts])  # Исключаем уже выбранные посты
                ).group_by(Post.post_id, User.user_id).order_by(func.count(Like.like_id).desc()).limit(remaining_limit).all()
                
                posts.extend(popular_posts)
            
            # Получаем детальную информацию о постах
            posts_with_details = []
            for post, user in posts:
                # Получаем количество лайков
                likes_count = db.query(func.count(Like.like_id)).filter(Like.post_id == post.post_id).scalar()
                
                # Получаем теги поста
                tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post.post_id).all()
                
                # Получаем комментарии первого уровня
                comments = db.query(Post).filter(Post.child_id == post.post_id).order_by(Post.creation_date).all()
                
                # Формируем структуру комментариев с вложенными ответами
                def get_comment_replies(comment_id):
                    replies = db.query(Post).filter(Post.child_id == comment_id).order_by(Post.creation_date).all()
                    replies_with_nested = []
                    
                    for reply in replies:
                        sub_replies = get_comment_replies(reply.post_id)
                        reply_dict = {
                            "post_id": reply.post_id,
                            "content": reply.content,
                            "child_id": reply.child_id,
                            "user_id": reply.user_id,
                            "media_link": reply.media_link,
                            "creation_date": reply.creation_date,
                            "views_count": reply.views_count,
                            "post_type_id": reply.post_type_id,
                            "replies": sub_replies
                        }
                        replies_with_nested.append(reply_dict)
                    
                    return replies_with_nested
                
                # Формируем список комментариев с вложенными ответами
                comments_with_replies = []
                for comment in comments:
                    replies = get_comment_replies(comment.post_id)
                    comment_dict = {
                        "post_id": comment.post_id,
                        "content": comment.content,
                        "child_id": comment.child_id,
                        "user_id": comment.user_id,
                        "media_link": comment.media_link,
                        "creation_date": comment.creation_date,
                        "views_count": comment.views_count,
                        "post_type_id": comment.post_type_id,
                        "replies": replies
                    }
                    comments_with_replies.append(comment_dict)
                
                # Формируем детальную информацию о посте
                post_dict = {
                    "post_id": post.post_id,
                    "content": post.content,
                    "child_id": post.child_id,
                    "user_id": post.user_id,
                    "user_name": user.name,
                    "user_image": user.image_link,
                    "media_link": post.media_link,
                    "creation_date": post.creation_date,
                    "views_count": post.views_count,
                    "post_type_id": post.post_type_id,
                    "likes_count": likes_count,
                    "tags": tags,
                    "comments": comments_with_replies
                }
                
                posts_with_details.append(post_dict)
            
            return posts_with_details
            
        except Exception as e:
            logger.error(f"Error getting recommended posts: {str(e)}")
            raise

    @staticmethod
    def get_user_details(db: Session, user_id: int):
        """
        Получает подробную информацию о пользователе, включая его теги, 
        количество постов и лайков.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
            
        Returns:
            dict: Словарь с подробной информацией о пользователе
        """
        try:
            # Получаем пользователя
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                return None
            
            # Получаем теги пользователя
            tags = db.query(Tag).join(TagForUser).filter(TagForUser.user_id == user_id).all()
            
            # Получаем количество постов пользователя
            post_count = db.query(func.count(Post.post_id)).filter(Post.user_id == user_id).scalar()
            
            # Получаем количество лайков, которые получили посты пользователя
            likes_count = db.query(func.count(Like.like_id)).join(Post).filter(Post.user_id == user_id).scalar()
            
            # Получаем тип профиля пользователя
            profile_type = db.query(ProfileType).filter(ProfileType.type_id == user.type_id).first()
            
            # Создаем словарь с данными пользователя
            user_details = {
                "user_id": user.user_id,
                "login": user.login,
                "name": user.name,
                "type_id": user.type_id,
                "profile_type": profile_type.name if profile_type else None,
                "image_link": user.image_link,
                "description": user.description,
                "rating": user.rating,
                "tags": tags,
                "post_count": post_count,
                "likes_count": likes_count
            }
            
            return user_details
        except Exception as e:
            logger.error(f"Error getting user details for user ID {user_id}: {str(e)}")
            raise

    @staticmethod
    def get_posts_with_details(db: Session, skip: int = 0, limit: int = 100):
        """
        Получает список постов с детальной информацией о лайках и комментариях.
        """
        try:
            # Получаем базовый список постов
            posts = db.query(Post).filter(
                Post.child_id.is_(None),  # Только основные посты
                Post.post_type_id == 1    # Только посты (не комментарии)
            ).order_by(desc(Post.creation_date)).offset(skip).limit(limit).all()
            
            # Для каждого поста получаем детальную информацию
            posts_with_details = []
            for post in posts:
                # Получаем количество лайков
                likes_count = db.query(func.count(Like.like_id)).filter(Like.post_id == post.post_id).scalar()
                
                # Получаем теги поста
                tags = db.query(Tag).join(TagForPost).filter(TagForPost.post_id == post.post_id).all()
                
                # Получаем комментарии первого уровня
                comments = db.query(Post).filter(Post.child_id == post.post_id).order_by(Post.creation_date).all()
                
                # Формируем структуру комментариев с вложенными ответами
                def get_comment_replies(comment_id):
                    replies = db.query(Post).filter(Post.child_id == comment_id).order_by(Post.creation_date).all()
                    replies_with_nested = []
                    
                    for reply in replies:
                        sub_replies = get_comment_replies(reply.post_id)
                        reply_dict = {
                            "post_id": reply.post_id,
                            "content": reply.content,
                            "child_id": reply.child_id,
                            "user_id": reply.user_id,
                            "media_link": reply.media_link,
                            "creation_date": reply.creation_date,
                            "views_count": reply.views_count,
                            "post_type_id": reply.post_type_id,
                            "replies": sub_replies
                        }
                        replies_with_nested.append(reply_dict)
                    
                    return replies_with_nested
                
                # Формируем список комментариев с вложенными ответами
                comments_with_replies = []
                for comment in comments:
                    replies = get_comment_replies(comment.post_id)
                    comment_dict = {
                        "post_id": comment.post_id,
                        "content": comment.content,
                        "child_id": comment.child_id,
                        "user_id": comment.user_id,
                        "media_link": comment.media_link,
                        "creation_date": comment.creation_date,
                        "views_count": comment.views_count,
                        "post_type_id": comment.post_type_id,
                        "replies": replies
                    }
                    comments_with_replies.append(comment_dict)
                
                # Формируем детальную информацию о посте
                post_dict = {
                    "post_id": post.post_id,
                    "content": post.content,
                    "child_id": post.child_id,
                    "user_id": post.user_id,
                    "media_link": post.media_link,
                    "creation_date": post.creation_date,
                    "views_count": post.views_count,
                    "post_type_id": post.post_type_id,
                    "likes_count": likes_count,
                    "tags": tags,
                    "comments": comments_with_replies
                }
                
                posts_with_details.append(post_dict)
            
            return posts_with_details
            
        except Exception as e:
            logger.error(f"Error getting posts with details: {str(e)}")
            raise 