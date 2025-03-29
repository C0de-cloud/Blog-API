from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

from app.models.user import UserRole


class Token(BaseModel):
    """Модель JWT токена"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Данные, хранящиеся в JWT токене"""
    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    expires: datetime 