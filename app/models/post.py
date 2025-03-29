from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from app.models.user import UserPublic


class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    tags: List[str] = Field(default_factory=list)
    slug: Optional[str] = None


class PostCreate(PostBase):
    status: PostStatus = PostStatus.DRAFT


class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    slug: Optional[str] = None
    status: Optional[PostStatus] = None


class PostInDB(PostBase):
    id: str
    author_id: str
    status: PostStatus
    created_at: datetime
    updated_at: datetime


class PostAuthor(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None


class Post(PostBase):
    id: str
    author: PostAuthor
    status: PostStatus
    created_at: datetime
    updated_at: datetime
    comments_count: int


class PostList(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Post] 