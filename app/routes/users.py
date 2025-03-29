from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, Body
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_database, get_current_user, get_current_admin_user, pagination_params
from app.crud.user import (
    get_user_by_id, get_users, get_users_count, update_user, delete_user
)
from app.crud.post import get_posts, get_posts_count
from app.crud.comment import get_user_comments, get_user_comments_count
from app.models.user import User, UserUpdate, UserRole, UserWithStats, UserPublic
from app.models.post import PostList
from app.models.comment import CommentList

router = APIRouter()


@router.get("/me", response_model=User)
async def read_users_me(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Получение информации о текущем пользователе."""
    return current_user


@router.get("/me/stats", response_model=UserWithStats)
async def read_users_me_stats(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Получение информации о текущем пользователе со статистикой."""
    user_id = current_user["id"]
    
    # Получение количества постов пользователя
    posts_count = await get_posts_count(db, {"author_id": user_id})
    
    # Получение количества комментариев пользователя
    comments_count = await get_user_comments_count(db, user_id)
    
    # Объединение данных
    return {
        **current_user,
        "posts_count": posts_count,
        "comments_count": comments_count
    }


@router.put("/me", response_model=User)
async def update_user_me(
    user_data: Annotated[UserUpdate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Обновление информации о текущем пользователе."""
    # Убеждаемся, что пользователь не может сам себе изменить роль
    if hasattr(user_data, "role") and user_data.role is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to change your own role"
        )
    
    updated_user = await update_user(db, current_user["id"], user_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update user"
        )
    return updated_user


@router.get("/me/posts", response_model=PostList)
async def read_users_me_posts(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    pagination: Annotated[dict, Depends(pagination_params)]
):
    """Получение постов текущего пользователя."""
    user_id = current_user["id"]
    
    # Получение постов с фильтрацией по ID автора
    posts = await get_posts(
        db, 
        pagination["limit"], 
        pagination["offset"], 
        {"author_id": user_id}
    )
    
    # Получение общего количества постов
    total = await get_posts_count(db, {"author_id": user_id})
    
    return {
        "total": total,
        "limit": pagination["limit"],
        "offset": pagination["offset"],
        "items": posts
    }


@router.get("/me/comments", response_model=CommentList)
async def read_users_me_comments(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    pagination: Annotated[dict, Depends(pagination_params)]
):
    """Получение комментариев текущего пользователя."""
    user_id = current_user["id"]
    
    # Получение комментариев пользователя
    comments = await get_user_comments(
        db, 
        user_id, 
        pagination["limit"], 
        pagination["offset"]
    )
    
    # Получение общего количества комментариев
    total = await get_user_comments_count(db, user_id)
    
    return {
        "total": total,
        "limit": pagination["limit"],
        "offset": pagination["offset"],
        "items": comments
    }


@router.get("", response_model=List[UserPublic])
async def read_users(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    pagination: Annotated[dict, Depends(pagination_params)],
    role: Annotated[Optional[UserRole], Query(None)] = None
):
    """Получение списка пользователей с пагинацией и фильтрацией по роли."""
    users = await get_users(
        db, 
        pagination["offset"], 
        pagination["limit"], 
        role
    )
    return users


@router.get("/{user_id}", response_model=UserPublic)
async def read_user(
    user_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Получение информации о пользователе по ID."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return user


@router.get("/{user_id}/stats", response_model=UserWithStats)
async def read_user_stats(
    user_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Получение информации о пользователе со статистикой."""
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Получение количества постов пользователя
    posts_count = await get_posts_count(db, {"author_id": user_id})
    
    # Получение количества комментариев пользователя
    comments_count = await get_user_comments_count(db, user_id)
    
    # Объединение данных
    return {
        **user,
        "posts_count": posts_count,
        "comments_count": comments_count
    }


@router.put("/{user_id}", response_model=User)
async def update_user_admin(
    user_id: Annotated[str, Path(...)],
    user_data: Annotated[UserUpdate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_admin_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """
    Обновление информации о пользователе.
    Только для администраторов.
    """
    updated_user = await update_user(db, user_id, user_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return updated_user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_admin(
    user_id: Annotated[str, Path(...)],
    current_user: Annotated[dict, Depends(get_current_admin_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """
    Удаление пользователя.
    Только для администраторов.
    """
    # Проверяем, не пытается ли админ удалить самого себя
    if current_user["id"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    success = await delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    return None 