from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status, Body
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import (
    get_database, get_current_user, get_current_editor_or_admin_user,
    pagination_params, post_filter_params
)
from app.crud.post import (
    get_post_by_id, get_post_by_slug, get_posts, get_posts_count,
    create_post, update_post, delete_post
)
from app.crud.comment import get_comments_by_post, get_comments_count_by_post
from app.models.post import Post, PostCreate, PostUpdate, PostList
from app.models.comment import CommentList

router = APIRouter()


@router.post("", response_model=Post, status_code=status.HTTP_201_CREATED)
async def create_post_route(
    post_data: Annotated[PostCreate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Создание нового поста."""
    return await create_post(db, post_data, current_user["id"])


@router.get("", response_model=PostList)
async def get_posts_route(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    pagination: Annotated[dict, Depends(pagination_params)],
    filters: Annotated[dict, Depends(post_filter_params)]
):
    """Получение списка постов с пагинацией и фильтрацией."""
    posts = await get_posts(db, pagination["limit"], pagination["offset"], filters)
    total = await get_posts_count(db, filters)
    
    return {
        "total": total,
        "limit": pagination["limit"],
        "offset": pagination["offset"],
        "items": posts
    }


@router.get("/{post_id}", response_model=Post)
async def get_post_by_id_route(
    post_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Получение поста по ID."""
    post = await get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found"
        )
    return post


@router.get("/slug/{slug}", response_model=Post)
async def get_post_by_slug_route(
    slug: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Получение поста по URL-slug."""
    post = await get_post_by_slug(db, slug)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with slug '{slug}' not found"
        )
    return post


@router.put("/{post_id}", response_model=Post)
async def update_post_route(
    post_id: Annotated[str, Path(...)],
    post_data: Annotated[PostUpdate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """
    Обновление поста.
    Пользователи могут обновлять только свои посты.
    Редакторы и администраторы могут обновлять любые посты.
    """
    # Проверка существования поста
    post = await get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found"
        )
    
    # Проверка прав на редактирование
    is_author = post.get("author", {}).get("id") == current_user["id"]
    is_editor_or_admin = current_user.get("role") in ["editor", "admin"]
    
    if not is_author and not is_editor_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this post"
        )
    
    # Обновление поста
    updated_post = await update_post(
        db, 
        post_id, 
        post_data, 
        current_user["id"] if not is_editor_or_admin else None
    )
    
    return updated_post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_route(
    post_id: Annotated[str, Path(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """
    Удаление поста.
    Пользователи могут удалять только свои посты.
    Редакторы и администраторы могут удалять любые посты.
    """
    # Проверка существования поста
    post = await get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found"
        )
    
    # Проверка прав на удаление
    is_author = post.get("author", {}).get("id") == current_user["id"]
    is_editor_or_admin = current_user.get("role") in ["editor", "admin"]
    
    if not is_author and not is_editor_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post"
        )
    
    # Удаление поста
    success = await delete_post(
        db, 
        post_id, 
        current_user["id"] if not is_editor_or_admin else None
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete post"
        )
    
    return None


@router.get("/{post_id}/comments", response_model=CommentList)
async def get_post_comments(
    post_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    pagination: Annotated[dict, Depends(pagination_params)],
    include_replies: Annotated[bool, Query(False)] = False
):
    """Получение комментариев к посту."""
    # Проверка существования поста
    post = await get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found"
        )
    
    # Получение комментариев
    comments = await get_comments_by_post(
        db, 
        post_id, 
        pagination["limit"], 
        pagination["offset"], 
        include_replies
    )
    
    # Получение общего количества комментариев
    total = await get_comments_count_by_post(db, post_id)
    
    return {
        "total": total,
        "limit": pagination["limit"],
        "offset": pagination["offset"],
        "items": comments
    } 