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
    filename: str = Field(
        ...,
        json_schema_extra={"example": "travel_policy_2026.txt"},
        description="Document filename with extension"
    )
    content: str = Field(
        ...,
        json_schema_extra={"example": "[Corporate Policy]\nEmployees are entitled to travel meal allowances..."},
        description="Raw document plain text content"
    )
    tenant_id: str = Field(
        "tenant_default",
        json_schema_extra={"example": "tenant_default"},
        description="Target tenant isolation space"
    )

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, summary="Asynchronous Document Ingestion Endpoint")
async def upload_document_async(
    req: DocumentUploadRequest,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    ## Asynchronous Document Ingestion (Celery + Redis Decoupled)
    - **Non-blocking Architecture**: Returns HTTP 202 Accepted immediately (<60ms)
    - **Tenant Anti-Spoofing**: Enforces authenticated user's real `tenant_id` if logged in
    """
    effective_tenant_id = current_user.tenant_id if current_user else req.tenant_id

    # 1. Register document metadata in database with PROCESSING state
    async with db_session.AsyncSessionLocal() as session:
        repo = VectorRepository(session)
        doc = await repo.create_document(
            tenant_id=effective_tenant_id,
            filename=req.filename,
            file_type="txt"
        )
        doc_id = doc.id

    # 2. Enqueue asynchronous chunking & embedding task to Celery
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
        "message": "Document accepted and enqueued for background processing. Poll status via task_id."
    }

@router.post("/admin/upload", status_code=status.HTTP_202_ACCEPTED, summary="[RBAC Protected] Admin Only Document Upload")
async def admin_upload_document(
    req: DocumentUploadRequest,
    current_user: User = Depends(require_admin)
):
    """
    ## Administrator Document Ingestion (Strict RBAC Guard)
    Requires valid JWT token bearing `admin` role in Authorization header; otherwise returns 401/403.
    """
    return await upload_document_async(req=req, current_user=current_user)

@router.get("/tasks/{task_id}", summary="Query Celery Task Status & Progress")
async def get_task_status(task_id: str):
    """
    ## Celery Task Status Polling Endpoint
    Returns states: PENDING -> PROCESSING -> SUCCESS / FAILURE
    """
    task_result = AsyncResult(task_id, app=celery_app)

    if task_result.state == "PENDING":
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": 0,
            "step": "Task enqueued, waiting for worker..."
        }
    elif task_result.state == "PROCESSING":
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": task_result.info.get("progress", 50) if isinstance(task_result.info, dict) else 50,
            "step": task_result.info.get("step", "Processing...") if isinstance(task_result.info, dict) else "Processing..."
        }
    elif task_result.state == "SUCCESS":
        result_data = task_result.result if isinstance(task_result.result, dict) else {}
        response = {
            "task_id": task_id,
            "state": task_result.state,
            "progress": 100,
            "step": "Document chunking and vector index completed successfully!",
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
