from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status

from app.models.comment import CommentCreate, CommentUpdate


async def get_comment_by_id(db: AsyncIOMotorDatabase, comment_id: str) -> Optional[Dict[str, Any]]:
    """Получение комментария по ID с информацией об авторе."""
    try:
        comment = await db.comments.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            return None
        
        # Получение информации об авторе
        author_id = comment.get("author_id")
        if author_id:
            author = await db.users.find_one({"_id": ObjectId(author_id)})
            if author:
                # Преобразуем _id автора в строку и удаляем пароль
                author["id"] = str(author["_id"])
                del author["_id"]
                if "password" in author:
                    del author["password"]
                
                # Оставляем только нужные поля для публичного профиля
                comment["author"] = {
                    "id": author["id"],
                    "username": author.get("username"),
                    "full_name": author.get("full_name"),
                    "bio": author.get("bio")
                }
                
                # Удаляем идентификатор автора, так как теперь у нас есть полные данные
                del comment["author_id"]
        
        # Преобразование _id в строку
        comment["id"] = str(comment["_id"])
        del comment["_id"]
        
        return comment
    except Exception:
        return None


async def get_comments_by_post(
    db: AsyncIOMotorDatabase,
    post_id: str,
    limit: int = 50,
    offset: int = 0,
    include_replies: bool = False
) -> List[Dict[str, Any]]:
    """Получение комментариев к посту с пагинацией."""
    # Подготовка запроса
    query = {"post_id": post_id}
    
    # Если не включаем ответы, показываем только корневые комментарии
    if not include_replies:
        query["parent_id"] = None
    
    # Выполнение запроса
    cursor = db.comments.find(query).sort("created_at", -1).skip(offset).limit(limit)
    
    comments = []
    async for comment in cursor:
        # Получаем полные данные о комментарии, включая автора
        full_comment = await get_comment_by_id(db, str(comment["_id"]))
        if full_comment:
            # Если это корневой комментарий и мы включаем ответы, добавляем их
            if include_replies and not comment.get("parent_id"):
                full_comment["replies"] = await get_comment_replies(db, str(comment["_id"]))
            
            comments.append(full_comment)
    
    return comments


async def get_comment_replies(
    db: AsyncIOMotorDatabase,
    parent_id: str
) -> List[Dict[str, Any]]:
    """Рекурсивное получение ответов на комментарий."""
    # Получение прямых ответов на комментарий
    cursor = db.comments.find({"parent_id": parent_id}).sort("created_at", 1)
    
    replies = []
    async for comment in cursor:
        # Получаем полные данные о комментарии, включая автора
        full_comment = await get_comment_by_id(db, str(comment["_id"]))
        if full_comment:
            # Рекурсивно получаем ответы на этот комментарий
            full_comment["replies"] = await get_comment_replies(db, str(comment["_id"]))
            replies.append(full_comment)
    
    return replies


async def get_comments_count_by_post(db: AsyncIOMotorDatabase, post_id: str) -> int:
    """Получение общего количества комментариев к посту."""
    return await db.comments.count_documents({"post_id": post_id})


async def create_comment(
    db: AsyncIOMotorDatabase,
    comment_data: CommentCreate,
    author_id: str
) -> Dict[str, Any]:
    """Создание нового комментария."""
    # Проверка существования поста
    post = await db.posts.find_one({"_id": ObjectId(comment_data.post_id)})
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Если указан родительский комментарий, проверяем его существование
    if comment_data.parent_id:
        parent_comment = await db.comments.find_one({
            "_id": ObjectId(comment_data.parent_id),
            "post_id": comment_data.post_id  # Убеждаемся, что родительский комментарий относится к тому же посту
        })
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent comment not found or belongs to different post"
            )
    
    # Подготовка данных
    comment_dict = comment_data.model_dump()
    now = datetime.utcnow()
    
    # Добавление служебных полей
    comment_dict["author_id"] = author_id
    comment_dict["created_at"] = now
    comment_dict["updated_at"] = now
    
    # Вставка в базу данных
    result = await db.comments.insert_one(comment_dict)
    
    # Получение созданного комментария
    return await get_comment_by_id(db, str(result.inserted_id))


async def update_comment(
    db: AsyncIOMotorDatabase,
    comment_id: str,
    comment_data: CommentUpdate,
    author_id: str
) -> Optional[Dict[str, Any]]:
    """Обновление комментария."""
    # Проверка существования комментария
    comment = await db.comments.find_one({"_id": ObjectId(comment_id)})
    if not comment:
        return None
    
    # Проверка прав доступа
    if comment.get("author_id") != author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this comment"
        )
    
    # Подготовка данных для обновления
    update_data = {k: v for k, v in comment_data.model_dump(exclude_unset=True).items() if v is not None}
    
    # Добавление времени обновления
    update_data["updated_at"] = datetime.utcnow()
    
    # Выполнение обновления
    await db.comments.update_one(
        {"_id": ObjectId(comment_id)},
        {"$set": update_data}
    )
    
    # Получение обновленного комментария
    return await get_comment_by_id(db, comment_id)


async def delete_comment(
    db: AsyncIOMotorDatabase,
    comment_id: str,
    author_id: Optional[str] = None,
    is_admin: bool = False
) -> bool:
    """Удаление комментария и всех ответов на него."""
    try:
        # Проверка существования комментария
        comment = await db.comments.find_one({"_id": ObjectId(comment_id)})
        if not comment:
            return False
        
        # Проверка прав доступа (если пользователь не админ)
        if not is_admin and author_id and comment.get("author_id") != author_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this comment"
            )
        
        # Рекурсивное удаление всех ответов
        await delete_comment_replies(db, comment_id)
        
        # Удаление самого комментария
        result = await db.comments.delete_one({"_id": ObjectId(comment_id)})
        return result.deleted_count > 0
    except Exception:
        return False


async def delete_comment_replies(db: AsyncIOMotorDatabase, parent_id: str) -> None:
    """Рекурсивное удаление всех ответов на комментарий."""
    # Получение идентификаторов всех прямых ответов
    cursor = db.comments.find({"parent_id": parent_id})
    
    # Для каждого ответа рекурсивно удаляем его ответы
    async for comment in cursor:
        comment_id = str(comment["_id"])
        await delete_comment_replies(db, comment_id)
        
        # Удаление самого ответа
        await db.comments.delete_one({"_id": ObjectId(comment_id)})


async def get_user_comments(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 20,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Получение комментариев пользователя с пагинацией."""
    # Выполнение запроса
    cursor = db.comments.find({"author_id": user_id}).sort("created_at", -1).skip(offset).limit(limit)
    
    comments = []
    async for comment in cursor:
        # Получаем полные данные о комментарии
        full_comment = await get_comment_by_id(db, str(comment["_id"]))
        if full_comment:
            # Добавляем информацию о посте
            post_id = full_comment.get("post_id")
            if post_id:
                post = await db.posts.find_one({"_id": ObjectId(post_id)})
                if post:
                    full_comment["post_title"] = post.get("title")
            
            comments.append(full_comment)
    
    return comments


async def get_user_comments_count(db: AsyncIOMotorDatabase, user_id: str) -> int:
    """Получение общего количества комментариев пользователя."""
    return await db.comments.count_documents({"author_id": user_id}) 