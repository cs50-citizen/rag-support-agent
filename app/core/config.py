import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Enterprise RAG Knowledge Base & Autonomous Support Agent"
    API_V1_STR: str = "/api/v1"
    GEMINI_API_KEY: str = ""
    
    # JWT Security & Authentication Settings
    JWT_SECRET_KEY: str = "enterprise_rag_super_secret_jwt_key_2026_xyz"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours validity
    
    # Database & Task Queue Connections
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/rag_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
