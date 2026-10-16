from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.rag_service import rag_service

router = APIRouter()

class ChatRequest(BaseModel):
    query: str = Field(..., example="我出差去上海，餐饮补贴每天多少钱？", description="用户问题")
    tenant_id: str = Field("tenant_default", example="corp_finance", description="多租户隔离标识")

@router.post("/chat/stream", summary="SSE 流式打字机问答接口")
async def chat_stream(request: ChatRequest):
    """
    ## Server-Sent Events (SSE) 流式问答接口
    - **请求方式**: POST
    - **响应媒体类型**: `text/event-stream`
    - **数据事件**:
      - `retrieving`: 正在检索知识库
      - `token`: 单个字符/Token打字机流式增量
      - `done`: 回答完成，返回参考资料来源
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
            "X-Accel-Buffering": "no"  # 关键：告知 Nginx 代理不要对流进行缓冲，实现真正的实时流
        }
    )

