from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, validator


class UserRole(str, Enum):
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @validator("password")
    def password_strength(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[UserRole] = None


class UserInDB(UserBase):
    id: str
    role: UserRole = UserRole.USER
    created_at: datetime
    updated_at: datetime
    password: str


class User(UserBase):
    id: str
    role: UserRole
    created_at: datetime
    updated_at: datetime


class UserPublic(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    role: UserRole
    created_at: datetime


class UserWithStats(User):
    posts_count: int
    comments_count: int 