from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException, status

from app.core.security import verify_password, get_password_hash
from app.models.user import UserCreate, UserUpdate, UserRole


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict[str, Any]]:
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None
        
        user["id"] = str(user["_id"])
        del user["_id"]
        
        if "password" in user:
            del user["password"]
        
        return user
    except Exception:
        return None


async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[Dict[str, Any]]:
    user = await db.users.find_one({"email": email})
    if not user:
        return None
    
    user["id"] = str(user["_id"])
    del user["_id"]
    
    return user


async def get_user_by_username(db: AsyncIOMotorDatabase, username: str) -> Optional[Dict[str, Any]]:
    user = await db.users.find_one({"username": username})
    if not user:
        return None
    
    user["id"] = str(user["_id"])
    del user["_id"]
    
    return user


async def get_users(
    db: AsyncIOMotorDatabase, 
    skip: int = 0, 
    limit: int = 10,
    role: Optional[UserRole] = None
) -> List[Dict[str, Any]]:
    query = {}
    if role:
        query["role"] = role
    
    cursor = db.users.find(query).skip(skip).limit(limit)
    
    users = []
    async for user in cursor:
        user["id"] = str(user["_id"])
        del user["_id"]
        
        if "password" in user:
            del user["password"]
        
        users.append(user)
    
    return users


async def get_users_count(db: AsyncIOMotorDatabase, role: Optional[UserRole] = None) -> int:
    query = {}
    if role:
        query["role"] = role
    
    return await db.users.count_documents(query)


async def create_user(db: AsyncIOMotorDatabase, user_data: UserCreate) -> Dict[str, Any]:
    if await get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    if await get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    user_dict = user_data.model_dump()
    now = datetime.utcnow()
    
    hashed_password = get_password_hash(user_dict["password"])
    user_dict["password"] = hashed_password
    user_dict["role"] = UserRole.USER
    user_dict["created_at"] = now
    user_dict["updated_at"] = now
    
    result = await db.users.insert_one(user_dict)
    
    created_user = await get_user_by_id(db, str(result.inserted_id))
    return created_user


async def update_user(
    db: AsyncIOMotorDatabase, 
    user_id: str, 
    user_data: UserUpdate
) -> Optional[Dict[str, Any]]:
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_data = {k: v for k, v in user_data.model_dump(exclude_unset=True).items() if v is not None}
    
    if "email" in update_data and update_data["email"] != user["email"]:
        if await get_user_by_email(db, update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    if "username" in update_data and update_data["username"] != user["username"]:
        if await get_user_by_username(db, update_data["username"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    
    return await get_user_by_id(db, user_id)


async def delete_user(db: AsyncIOMotorDatabase, user_id: str) -> bool:
    try:
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        return result.deleted_count > 0
    except Exception:
        return False


async def authenticate_user(
    db: AsyncIOMotorDatabase, 
    username_or_email: str, 
    password: str
) -> Optional[Dict[str, Any]]:
    user = await get_user_by_username(db, username_or_email)
    
    if not user:
        user = await get_user_by_email(db, username_or_email)
    
    if not user:
        return None
    
    user_with_password = await db.users.find_one({"_id": ObjectId(user["id"])})
    
    if not verify_password(password, user_with_password["password"]):
        return None
    
    return user


async def change_user_password(
    db: AsyncIOMotorDatabase,
    user_id: str,
    current_password: str,
    new_password: str
) -> bool:
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        return False
    
    if not verify_password(current_password, user["password"]):
        return False
    
    hashed_password = get_password_hash(new_password)
    
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"password": hashed_password, "updated_at": datetime.utcnow()}}
    )
    
    return True 