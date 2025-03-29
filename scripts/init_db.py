import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

from app.core.security import get_password_hash
from app.models.user import UserRole

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "blog_db")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")


async def init_db():
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DB_NAME]
    
    print("Creating indexes...")
    
    await db.posts.create_index("slug", unique=True)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    
    print("Creating admin user...")
    
    # Проверка существования админа
    existing_admin = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing_admin:
        print("Admin user already exists")
    else:
        admin_user = {
            "username": ADMIN_USERNAME,
            "email": ADMIN_EMAIL,
            "password": get_password_hash(ADMIN_PASSWORD),
            "full_name": ADMIN_NAME,
            "role": UserRole.ADMIN,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        result = await db.users.insert_one(admin_user)
        if result.inserted_id:
            print(f"Admin user created with ID: {result.inserted_id}")
        else:
            print("Failed to create admin user")
    
    print("Database initialization completed")
    
    client.close()


if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(init_db()) 