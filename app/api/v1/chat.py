from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.rag_service import rag_service

router = APIRouter()

class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        json_schema_extra={"example": "What is the daily meal allowance for business trips to Tier-1 cities?"},
        description="User query string"
    )
    tenant_id: str = Field(
        "tenant_default",
        json_schema_extra={"example": "tenant_default"},
        description="Multi-tenant isolation identifier"
    )

@router.post("/chat/stream", summary="SSE Streaming Typewriter Endpoint")
async def chat_stream(request: ChatRequest):
    """
    ## Server-Sent Events (SSE) Streaming Chat Endpoint
    - **Method**: POST
    - **Media Type**: `text/event-stream`
    - **Lifecycle Events**:
      - `intent`: Pre-filtering classification (`CHITCHAT`, `ACTION_TOOL`, `KNOWLEDGE_QUERY`)
      - `retrieving`: Searching multi-tenant vector chunks
      - `compression`: Context pruning token reduction stats
      - `token`: Incremental typewriter character/token chunks
      - `done`: Finalization event with evidence references
    """
    generator = rag_service.stream_rag_answer(
        query=request.query,
        tenant_id=request.tenant_id
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Critical: Disables reverse proxy stream buffering (e.g. Nginx)
        }
    )
