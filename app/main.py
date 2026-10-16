from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.auth import router as auth_router
from app.services.rag_service import rag_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 服务启动：初始化数据库并完成默认租户向量表播种
    await rag_service.initialize_database_and_seed()
    yield
    # 服务关闭清理 (如果需要)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="企业级 RAG 知识库与智能助手后端 API，支持 SSE 流式打字机响应与多租户隔离架构。",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置跨域资源共享 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(documents_router, prefix=settings.API_V1_STR)

import os
from fastapi.responses import FileResponse

@app.get("/", summary="React 知识库与智能助手控制台")
@app.get("/app", summary="React 知识库与智能助手控制台")
async def serve_frontend():
    index_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "message": f"欢迎使用 {settings.PROJECT_NAME} API 服务！",
        "docs_url": "/docs",
        "health_check": "/health"
    }

@app.get("/health", summary="健康检查接口")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0"
    }
