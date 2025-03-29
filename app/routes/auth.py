from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_database, get_current_user
from app.core.security import create_access_token
from app.core.config import get_token_expire_time
from app.crud.user import authenticate_user, create_user, change_user_password
from app.models.auth import Token
from app.models.user import User, UserCreate

router = APIRouter()


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: Annotated[UserCreate, Body(...)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Регистрация нового пользователя."""
    return await create_user(db, user_data)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """
    Авторизация пользователя с использованием OAuth2 для получения JWT токена.
    Принимает имя пользователя/email и пароль.
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_expires = get_token_expire_time()
    access_token = create_access_token(
        data={
            "sub": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"]
        },
        expires_delta=token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh-token", response_model=Token)
async def refresh_token(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """Обновление JWT токена для текущего пользователя."""
    token_expires = get_token_expire_time()
    access_token = create_access_token(
        data={
            "sub": current_user["id"],
            "username": current_user["username"],
            "email": current_user["email"],
            "role": current_user["role"]
        },
        expires_delta=token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    current_password: Annotated[str, Body(...)],
    new_password: Annotated[str, Body(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)]
):
    """Изменение пароля текущего пользователя."""
    success = await change_user_password(
        db, 
        current_user["id"], 
        current_password, 
        new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    return {"message": "Password changed successfully"} 