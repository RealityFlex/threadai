from sqlalchemy.orm import Session
from sqlalchemy import func, text, desc, and_, or_, distinct
from app.models.models import Post, Like, TagForPost, Tag, User, PostType, TagForUser, ProfileType
from app.schemas.post_schemas import PostCreate, PostUpdate, LikeCreate, CommentWithReplies
import sys
import os
import logging
from collections import Counter
from datetime import datetime, timedelta

# Добавляем корневую директорию проекта в sys.path для импорта tokens.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from tokens import extract_topic_tokens

# Получаем логгер
logger = logging.getLogger("app")

class PostService:
    @staticmethod
    def create_post(db: Session, post_data: PostCreate):
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
            
            # Получаем максимальное значение post_id и прибавляем 1
            max_id = db.query(func.max(Post.post_id)).scalar() or 0
            next_id = max_id + 1
            
            # Создаем пост с явным указанием ID
            db_post = Post(
                post_id=next_id,
                content=post_data.content,
                child_id=post_data.child_id,
                user_id=post_data.user_id,
                media_link=post_data.media_link,
                post_type_id=post_data.post_type_id,
                creation_date=datetime.now()
            )
            print(datetime.now())
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
        return db.query(Post).filter(Post.child_id.is_(None)).order_by(desc(Post.creation_date)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_comments(db: Session, post_id: int, skip: int = 0, limit: int = 100):
        return db.query(Post).filter(Post.child_id == post_id).order_by(Post.creation_date).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_post(db: Session, post_id: int, post_data: PostUpdate):
        try:
            db_post = db.query(Post).filter(Post.post_id == post_id).first()
            if db_post:
                # Обновляем только переданные поля
                for key, value in post_data.model_dump(exclude_unset=True).items():
                    setattr(db_post, key, value)
                
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
        Получает рекомендованные посты для пользователя на основе его интересов (тегов).
        
        Алгоритм рекомендаций основан на следующих факторах:
        1. Совпадение тегов с интересами пользователя
        2. Популярность постов (количество лайков)
        3. Новизна постов (недавно созданные)
        4. Исключение постов, которые пользователь уже лайкнул
        
        Система всегда возвращает посты, даже если нет точных совпадений по тегам.
        
        Args:
            db (Session): Сессия базы данных
            user_id (int): ID пользователя
            skip (int): Сколько постов пропустить
            limit (int): Сколько постов вернуть
            
        Returns:
            list: Список рекомендованных постов
        """
        try:
            # Получаем ID постов, которые пользователь уже лайкнул
            liked_post_ids = db.query(Like.post_id).filter(Like.user_id == user_id).all()
            liked_post_ids = [post_id[0] for post_id in liked_post_ids]
            
            # Формируем базовый запрос для постов, которые можно рекомендовать
            base_query = db.query(Post).filter(
                Post.child_id.is_(None),  # Только основные посты, не комментарии
                Post.post_type_id == 1,   # Только посты (не комментарии и не репосты)
                Post.user_id != user_id   # Исключаем посты самого пользователя
            )
            
            # Исключаем посты, которые пользователь уже лайкнул
            if liked_post_ids:
                base_query = base_query.filter(~Post.post_id.in_(liked_post_ids))
            
            # Получаем теги пользователя (его интересы)
            user_tag_ids = db.query(TagForUser.tag_id).filter(TagForUser.user_id == user_id).all()
            user_tag_ids = [tag_id[0] for tag_id in user_tag_ids]
            
            # Если у пользователя нет тегов, обновляем их на основе лайков
            if not user_tag_ids:
                PostService.update_user_tags_from_likes(db, user_id)
                user_tag_ids = db.query(TagForUser.tag_id).filter(TagForUser.user_id == user_id).all()
                user_tag_ids = [tag_id[0] for tag_id in user_tag_ids]
            
            # Начинаем формировать список рекомендованных постов
            recommended_posts = []
            
            # Если у пользователя есть теги, сначала находим посты, соответствующие его интересам
            if user_tag_ids:
                # Находим посты с совпадающими тегами
                tagged_posts_query = base_query.join(
                    TagForPost, Post.post_id == TagForPost.post_id
                ).filter(
                    TagForPost.tag_id.in_(user_tag_ids)
                ).distinct()
                
                # Вычисляем "рейтинг" поста путем подсчета количества совпадающих тегов
                subquery = db.query(
                    TagForPost.post_id,
                    func.count(TagForPost.tag_id).label('matching_tags')
                ).filter(
                    TagForPost.tag_id.in_(user_tag_ids)
                ).group_by(TagForPost.post_id).subquery()
                
                # Получаем количество лайков для каждого поста
                likes_count_subquery = db.query(
                    Like.post_id,
                    func.count(Like.like_id).label('likes_count')
                ).group_by(Like.post_id).subquery()
                
                # Объединяем данные и вычисляем итоговый рейтинг
                tagged_posts = db.query(
                    Post,
                    subquery.c.matching_tags,
                    func.coalesce(likes_count_subquery.c.likes_count, 0).label('likes_count')
                ).outerjoin(
                    subquery, Post.post_id == subquery.c.post_id
                ).outerjoin(
                    likes_count_subquery, Post.post_id == likes_count_subquery.c.post_id
                ).filter(
                    Post.post_id.in_([p.post_id for p in tagged_posts_query])
                ).order_by(
                    # Сначала сортируем по количеству совпадающих тегов
                    desc(subquery.c.matching_tags),
                    # Затем по новизне (чем новее, тем выше)
                    desc(Post.creation_date),
                    # И наконец по популярности
                    desc(func.coalesce(likes_count_subquery.c.likes_count, 0))
                ).offset(skip).limit(limit).all()
                
                # Добавляем посты с совпадающими тегами в начало списка рекомендаций
                recommended_posts.extend([post for post, _, _ in tagged_posts])
            
            # Если не хватает постов с тегами, добавляем самые популярные и новые посты
            if len(recommended_posts) < limit:
                # Определяем, сколько еще постов нужно добавить
                remaining_limit = limit - len(recommended_posts)
                remaining_skip = max(0, skip - len(recommended_posts))
                
                # Исключаем уже добавленные посты
                existing_post_ids = [post.post_id for post in recommended_posts]
                popular_posts_query = base_query
                
                if existing_post_ids:
                    popular_posts_query = popular_posts_query.filter(~Post.post_id.in_(existing_post_ids))
                
                # Получаем популярные и новые посты, которые еще не вошли в рекомендации
                popular_posts = popular_posts_query.outerjoin(Like).group_by(Post.post_id).order_by(
                    func.count(Like.like_id).desc(),  # Сначала по количеству лайков
                    desc(Post.creation_date)          # Затем по новизне
                ).offset(remaining_skip).limit(remaining_limit).all()
                
                # Добавляем популярные посты в конец списка рекомендаций
                recommended_posts.extend(popular_posts)
            
            # Если рекомендации все равно пусты, добавляем случайные посты
            if not recommended_posts:
                # Получаем случайные посты в системе
                random_posts = base_query.order_by(func.random()).limit(limit).all()
                recommended_posts.extend(random_posts)
            
            # Возвращаем итоговый список рекомендаций
            return recommended_posts
        
        except Exception as e:
            logger.error(f"Error getting recommended posts for user ID {user_id}: {str(e)}")
            
            # В случае ошибки все равно пытаемся вернуть какие-то посты
            try:
                # Получаем самые новые посты
                fallback_posts = db.query(Post).filter(
                    Post.child_id.is_(None),  # Только основные посты, не комментарии
                    Post.post_type_id == 1    # Только посты (не комментарии и не репосты)
                ).order_by(desc(Post.creation_date)).limit(limit).all()
                
                return fallback_posts
            except:
                # Если и это не получается, возвращаем пустой список
                return []

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