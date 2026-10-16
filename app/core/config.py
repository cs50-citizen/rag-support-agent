import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise RAG Knowledge Base"
    API_V1_STR: str = "/api/v1"
    GEMINI_API_KEY: str = ""
    
    # JWT 安全与鉴权配置 (Milestone 6)
    JWT_SECRET_KEY: str = "enterprise_rag_super_secret_jwt_key_2026_xyz"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时过期
    
    # 数据库与任务队列配置
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/rag_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

