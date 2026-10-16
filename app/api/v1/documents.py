from typing import Optional
from fastapi import APIRouter, status, HTTPException, Depends
from pydantic import BaseModel, Field
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.tasks.document_tasks import process_document_task
from app.repositories.vector_repo import VectorRepository
from app.api.deps import get_current_user_optional, require_admin
from app.models.schema import User
import app.db.session as db_session

router = APIRouter(prefix="/documents", tags=["Documents & Tasks"])

class DocumentUploadRequest(BaseModel):
    filename: str = Field(..., example="product_manual_2026.txt", description="文档文件名")
    content: str = Field(..., example="[产品手册]\n新一代 AI 知识库支持多租户隔离与流式打字机问答...", description="文档纯文本内容")
    tenant_id: str = Field("tenant_default", example="corp_tech", description="租户所属空间")


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, summary="异步长文档上传与索引入口")
async def upload_document_async(
    req: DocumentUploadRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    ## 异步长文档入库端点 (Celery + Redis 异步解耦)
    - **非阻塞设计**: 接收请求后立即返回 HTTP 202，不占用 Web 线程
    - **租户防伪造**: 若已登录认证，则强制绑定登录用户的真实 `tenant_id`
    """
    effective_tenant_id = current_user.tenant_id if current_user else req.tenant_id

    # 1. 在数据库中登记文档元数据，状态设为 PENDING
    async with db_session.AsyncSessionLocal() as session:
        repo = VectorRepository(session)
        doc = await repo.create_document(
            tenant_id=effective_tenant_id,
            filename=req.filename,
            file_type="txt"
        )
        doc_id = doc.id

    # 2. 将耗时解析任务推送至 Celery 任务队列
    task = process_document_task.delay(
        document_id=doc_id,
        tenant_id=effective_tenant_id,
        file_content=req.content,
        filename=req.filename
    )

    return {
        "status": "ACCEPTED",
        "document_id": doc_id,
        "task_id": task.id,
        "tenant_id": effective_tenant_id,
        "message": "文档已成功接收并压入后台异步任务队列，请通过 task_id 轮询解析进度"
    }


@router.post("/admin/upload", status_code=status.HTTP_202_ACCEPTED, summary="[RBAC 严格权限] 仅管理员角色可上传入库")
async def admin_upload_document(
    req: DocumentUploadRequest,
    current_user: User = Depends(require_admin)
):
    """
    ## 严格管理员长文档上传入库 (强制 RBAC 校验)
    必须在 Header 中携带属于 `admin` 角色的合法 JWT Token，否则返回 401 / 403
    """
    return await upload_document_async(req=req, current_user=current_user)


@router.get("/tasks/{task_id}", summary="查询 Celery 异步任务处理状态")
async def get_task_status(task_id: str):
    """
    ## 任务状态与进度轮询端点
    返回状态: PENDING (排队中) -> PROCESSING (解析切片/向量化中) -> SUCCESS (成功) / FAILURE (失败)
    """
    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.state == "PENDING":
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": 0,
            "step": "任务已入队，等待 Worker 调度..."
        }
    elif task_result.state == "PROCESSING":
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": task_result.info.get("progress", 50) if isinstance(task_result.info, dict) else 50,
            "step": task_result.info.get("step", "正在处理中...") if isinstance(task_result.info, dict) else "处理中"
        }
    elif task_result.state == "SUCCESS":
        result_data = task_result.result if isinstance(task_result.result, dict) else {}
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": 100,
            "step": "文档切片与向量索引构建完成！",
            "result": result_data
        }
    elif task_result.state == "FAILURE":
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": 0,
            "error": str(task_result.info)
        }
    else:
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "info": str(task_result.info)
        }

    return response
