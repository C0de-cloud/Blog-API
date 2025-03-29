from typing import Annotated, Dict
from jose import JWTError, jwt

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.db.mongodb import get_database
from app.models.user import UserRole
from app.crud.user import get_user_by_id

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_admin_user(
    current_user: Annotated[Dict, Depends(get_current_user)]
) -> Dict:
    if current_user["role"] != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user


async def get_current_editor_or_admin_user(
    current_user: Annotated[Dict, Depends(get_current_user)]
) -> Dict:
    if current_user["role"] not in [UserRole.EDITOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user


async def pagination_params(
    limit: Annotated[int, Query(10, ge=1, le=100)],
    offset: Annotated[int, Query(0, ge=0)]
) -> Dict:
    return {"limit": limit, "offset": offset}


async def post_filter_params(
    status: Annotated[str, Query(None)],
    tag: Annotated[str, Query(None)],
    author_id: Annotated[str, Query(None)]
) -> Dict:
    filters = {}
    if status:
        filters["status"] = status
    if tag:
        filters["tags"] = tag
    if author_id:
        filters["author_id"] = author_id
    return filters 