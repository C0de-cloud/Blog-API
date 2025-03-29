from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status

from app.core.utils import generate_slug, is_valid_slug, get_summary_from_content
from app.models.post import PostCreate, PostUpdate, PostStatus


async def get_post_by_id(db: AsyncIOMotorDatabase, post_id: str) -> Optional[Dict[str, Any]]:
    """Получение поста по ID с информацией об авторе."""
    try:
        post = await db.posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            return None
        
        # Получение информации об авторе
        author_id = post.get("author_id")
        if author_id:
            author = await db.users.find_one({"_id": ObjectId(author_id)})
            if author:
                # Преобразуем _id автора в строку и удаляем пароль
                author["id"] = str(author["_id"])
                del author["_id"]
                if "password" in author:
                    del author["password"]
                
                # Оставляем только нужные поля для публичного профиля
                post["author"] = {
                    "id": author["id"],
                    "username": author.get("username"),
                    "full_name": author.get("full_name"),
                    "bio": author.get("bio")
                }
                
                # Удаляем идентификатор автора, так как теперь у нас есть полные данные
                del post["author_id"]
        
        # Получение количества комментариев
        comments_count = await db.comments.count_documents({"post_id": str(post["_id"])})
        post["comments_count"] = comments_count
        
        # Преобразование _id в строку
        post["id"] = str(post["_id"])
        del post["_id"]
        
        return post
    except Exception:
        return None


async def get_post_by_slug(db: AsyncIOMotorDatabase, slug: str) -> Optional[Dict[str, Any]]:
    """Получение поста по URL-slug."""
    post = await db.posts.find_one({"slug": slug})
    if not post:
        return None
    
    # Получаем полные данные поста с автором
    return await get_post_by_id(db, str(post["_id"]))


async def get_posts(
    db: AsyncIOMotorDatabase,
    limit: int = 10,
    offset: int = 0,
    filters: Dict = None
) -> List[Dict[str, Any]]:
    """Получение списка постов с пагинацией и фильтрацией."""
    # Подготовка фильтра
    query = {}
    if filters:
        if "status" in filters:
            query["status"] = filters["status"]
        
        if "tags" in filters:
            query["tags"] = filters["tags"]
        
        if "author_id" in filters:
            query["author_id"] = filters["author_id"]
    
    # По умолчанию показываем только опубликованные посты
    if "status" not in query:
        query["status"] = PostStatus.PUBLISHED
    
    # Выполнение запроса с сортировкой по дате создания (сначала новые)
    cursor = db.posts.find(query).sort("created_at", -1).skip(offset).limit(limit)
    
    posts = []
    async for post in cursor:
        # Получаем полные данные о посте, включая автора и счетчик комментариев
        full_post = await get_post_by_id(db, str(post["_id"]))
        if full_post:
            posts.append(full_post)
    
    return posts


async def get_posts_count(db: AsyncIOMotorDatabase, filters: Dict = None) -> int:
    """Получение общего количества постов с учетом фильтров."""
    # Подготовка фильтра
    query = {}
    if filters:
        if "status" in filters:
            query["status"] = filters["status"]
        
        if "tags" in filters:
            query["tags"] = filters["tags"]
        
        if "author_id" in filters:
            query["author_id"] = filters["author_id"]
    
    # По умолчанию показываем только опубликованные посты
    if "status" not in query:
        query["status"] = PostStatus.PUBLISHED
    
    return await db.posts.count_documents(query)


async def create_post(
    db: AsyncIOMotorDatabase,
    post_data: PostCreate,
    author_id: str
) -> Dict[str, Any]:
    """Создание нового поста."""
    # Подготовка данных
    post_dict = post_data.model_dump()
    now = datetime.utcnow()
    
    # Генерация slug, если он не указан
    if not post_dict.get("slug"):
        post_dict["slug"] = generate_slug(post_dict["title"])
    elif not is_valid_slug(post_dict["slug"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid slug format"
        )
    
    # Проверка уникальности slug
    existing_post = await db.posts.find_one({"slug": post_dict["slug"]})
    if existing_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post with this slug already exists"
        )
    
    # Генерация summary из content, если он не указан
    if not post_dict.get("summary"):
        post_dict["summary"] = get_summary_from_content(post_dict["content"])
    
    # Добавление служебных полей
    post_dict["author_id"] = author_id
    post_dict["created_at"] = now
    post_dict["updated_at"] = now
    
    # Вставка в базу данных
    result = await db.posts.insert_one(post_dict)
    
    # Получение созданного поста
    return await get_post_by_id(db, str(result.inserted_id))


async def update_post(
    db: AsyncIOMotorDatabase,
    post_id: str,
    post_data: PostUpdate,
    author_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Обновление поста."""
    # Проверка существования поста
    post = await db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return None
    
    # Проверка прав доступа (если передан ID автора)
    if author_id and post.get("author_id") != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this post"
        )
    
    # Подготовка данных для обновления
    update_data = {k: v for k, v in post_data.model_dump(exclude_unset=True).items() if v is not None}
    
    # Обработка slug, если он изменяется
    if "slug" in update_data:
        if not update_data["slug"]:
            update_data["slug"] = generate_slug(update_data.get("title") or post.get("title"))
        elif not is_valid_slug(update_data["slug"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid slug format"
            )
        
        # Проверка уникальности нового slug
        if update_data["slug"] != post.get("slug"):
            existing_post = await db.posts.find_one({"slug": update_data["slug"]})
            if existing_post:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Post with this slug already exists"
                )
    
    # Обработка summary, если контент изменяется
    if "content" in update_data and "summary" not in update_data:
        update_data["summary"] = get_summary_from_content(update_data["content"])
    
    # Добавление времени обновления
    update_data["updated_at"] = datetime.utcnow()
    
    # Выполнение обновления
    await db.posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": update_data}
    )
    
    # Получение обновленного поста
    return await get_post_by_id(db, post_id)


async def delete_post(
    db: AsyncIOMotorDatabase,
    post_id: str,
    author_id: Optional[str] = None
) -> bool:
    """Удаление поста и всех связанных комментариев."""
    try:
        # Проверка существования поста
        post = await db.posts.find_one({"_id": ObjectId(post_id)})
        if not post:
            return False
        
        # Проверка прав доступа (если передан ID автора)
        if author_id and post.get("author_id") != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this post"
            )
        
        # Удаление всех комментариев к посту
        await db.comments.delete_many({"post_id": post_id})
        
        # Удаление поста
        result = await db.posts.delete_one({"_id": ObjectId(post_id)})
        return result.deleted_count > 0
    except Exception:
        return False 