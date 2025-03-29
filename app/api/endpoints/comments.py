from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, status, Body
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_database, get_current_user, get_current_admin_user
from app.crud.comment import (
    get_comment_by_id, create_comment, update_comment, 
    delete_comment, get_comment_replies
)
from app.models.comment import Comment, CommentCreate, CommentUpdate, CommentWithReplies

router = APIRouter()


@router.post("", response_model=Comment, status_code=status.HTTP_201_CREATED)
async def create_comment_route(
    comment_data: Annotated[CommentCreate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    return await create_comment(db, comment_data, current_user["id"])


@router.get("/{comment_id}", response_model=Comment)
async def get_comment_route(
    comment_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with ID {comment_id} not found"
        )
    return comment


@router.get("/{comment_id}/replies", response_model=CommentWithReplies)
async def get_comment_with_replies_route(
    comment_id: Annotated[str, Path(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with ID {comment_id} not found"
        )
    
    replies = await get_comment_replies(db, comment_id)
    
    result = {**comment, "replies": replies}
    return result


@router.put("/{comment_id}", response_model=Comment)
async def update_comment_route(
    comment_id: Annotated[str, Path(...)],
    comment_data: Annotated[CommentUpdate, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with ID {comment_id} not found"
        )
    
    if comment.get("author", {}).get("id") != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this comment"
        )
    
    updated_comment = await update_comment(db, comment_id, comment_data, current_user["id"])
    
    return updated_comment


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment_route(
    comment_id: Annotated[str, Path(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with ID {comment_id} not found"
        )
    
    is_author = comment.get("author", {}).get("id") == current_user["id"]
    is_admin = current_user.get("role") == "admin"
    
    success = await delete_comment(
        db, 
        comment_id, 
        current_user["id"] if not is_admin else None,
        is_admin
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete comment"
        )
    
    return None 