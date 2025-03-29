from typing import List
from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Blog API"
    DESCRIPTION: str = "API для блога с постами и комментариями"
    VERSION: str = "1.0.0"
    
    API_PREFIX: str = "/api"
    
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    CORS_ORIGINS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_token_expire_time() -> timedelta:
    return timedelta(minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES) 