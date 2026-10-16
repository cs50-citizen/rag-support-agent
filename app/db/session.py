import os
import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.base import Base

logger = logging.getLogger("rag_db")

raw_db_url = settings.DATABASE_URL
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_local.db")
SQLITE_URL = f"sqlite+aiosqlite:///{db_path}"

# 初始判定
if raw_db_url.startswith("postgresql://") or raw_db_url.startswith("postgres://"):
    ASYNC_DATABASE_URL = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
    IS_POSTGRES = True
else:
    ASYNC_DATABASE_URL = SQLITE_URL
    IS_POSTGRES = False

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

async def init_db():
    """
    初始化数据库表结构：
    优先尝试连接配置的 PostgreSQL 5432 (pgvector)；
    若本地未启动 PostgreSQL 服务，则自动降级为 SQLite (自带多租户与向量检索)，确保项目随时可跑。
    """
    global engine, AsyncSessionLocal, IS_POSTGRES

    if IS_POSTGRES:
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.run_sync(Base.metadata.create_all)
            print("🐘 [数据库] 成功连接至 PostgreSQL 并激活 pgvector 向量插件！")
            return
        except Exception as e:
            print(f"⚠️  [数据库] 探测到 PostgreSQL 连接不可用 ({e})")
            print("🔄 [数据库] 正在自动降级为本地异步 SQLite 引擎 (支持多租户与向量检索)...")
            
            IS_POSTGRES = False
            engine = create_async_engine(SQLITE_URL, echo=False, future=True)
            AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    # SQLite 初始化
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("💾 [数据库] 本地数据库表结构与多租户索引就绪！")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入 Session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

