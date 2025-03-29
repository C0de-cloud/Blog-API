from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class CommentBase(BaseModel):
    content: str = Field(..., min_length=1)
    post_id: str


class CommentCreate(CommentBase):
    parent_id: Optional[str] = None


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class CommentAuthor(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None


class Comment(CommentBase):
    id: str
    author: CommentAuthor
    parent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CommentWithReplies(Comment):
    replies: List['CommentWithReplies'] = []


class CommentList(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Comment]


# Обновляем ссылку на себя для рекурсивной модели
CommentWithReplies.model_rebuild() 