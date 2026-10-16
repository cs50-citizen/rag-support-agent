import re
import asyncio
from typing import Dict, Any
from app.core.celery_app import celery_app
from app.services.rag_service import rag_service
import app.db.session as db_session
from app.repositories.vector_repo import VectorRepository

@celery_app.task(bind=True, name="process_document_task")
def process_document_task(self, document_id: int, tenant_id: str, file_content: str, filename: str) -> Dict[str, Any]:
    """
    Celery 异步长任务：
    负责解耦大文档的 1. 结构化切片 2. 向量化计算 3. PostgreSQL 批量入库
    支持状态更新: PENDING -> PROCESSING (progress 20% -> 60% -> 90%) -> SUCCESS
    """
    async def _run_async_pipeline():
        # 步骤 1: 文本预处理与分块 (Chunking)
        self.update_state(
            state="PROCESSING",
            meta={"progress": 20, "step": "正在解析文档结构并执行语义切块..."}
        )
        raw_chunks = [c.strip() for c in re.split(r"\n\s*\n", file_content) if c.strip()]
        if not raw_chunks:
            raw_chunks = [file_content.strip()]

        # 步骤 2: 批量向量化 (Embeddings)
        self.update_state(
            state="PROCESSING",
            meta={"progress": 60, "step": f"已切分 {len(raw_chunks)} 个片段，正在调用 Embedding 模型批量向量化..."}
        )
        chunks_data = []
        for idx, chunk_text in enumerate(raw_chunks):
            emb = rag_service.get_embedding(chunk_text)
            chunks_data.append({
                "content": chunk_text,
                "embedding": emb,
                "meta_info": {
                    "source": filename,
                    "chunk_index": idx,
                    "tenant_id": tenant_id
                }
            })

        # 步骤 3: 持久化入库 (PostgreSQL / SQLite)
        self.update_state(
            state="PROCESSING",
            meta={"progress": 85, "step": "正在持久化切片与向量至数据库..."}
        )
        async with db_session.AsyncSessionLocal() as session:
            repo = VectorRepository(session)
            await repo.save_chunks(tenant_id, document_id, chunks_data)

        return {
            "status": "SUCCESS",
            "progress": 100,
            "document_id": document_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "total_chunks": len(chunks_data)
        }

    # 执行异步协程并返回任务结果
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 兼容嵌套事件循环环境
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_run_async_pipeline())
        else:
            return asyncio.run(_run_async_pipeline())
    except RuntimeError:
        return asyncio.run(_run_async_pipeline())

