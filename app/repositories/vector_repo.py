from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import Tenant, Document, DocumentChunk
import app.db.session as db_session

class VectorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_tenant(self, tenant_id: str, name: str = "默认租户") -> Tenant:
        """确保租户存在"""
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(id=tenant_id, name=name)
            self.db.add(tenant)
            await self.db.commit()
            await self.db.refresh(tenant)
        return tenant

    async def create_document(self, tenant_id: str, filename: str, file_type: str = "txt") -> Document:
        """创建文档记录"""
        await self.get_or_create_tenant(tenant_id)
        doc = Document(
            tenant_id=tenant_id,
            filename=filename,
            file_type=file_type,
            status="PROCESSING"
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def save_chunks(
        self,
        tenant_id: str,
        document_id: int,
        chunks_data: List[Dict[str, Any]]
    ):
        """
        批量保存切片与向量数据，强制附带 tenant_id 实现隔离
        """
        db_chunks = []
        for idx, item in enumerate(chunks_data):
            chunk = DocumentChunk(
                tenant_id=tenant_id,
                document_id=document_id,
                chunk_index=idx,
                content=item["content"],
                meta_info=item.get("meta_info", {}),
                embedding=item.get("embedding")
            )
            db_chunks.append(chunk)

        self.db.add_all(db_chunks)

        # 更新主文档状态
        doc_stmt = select(Document).where(and_(Document.id == document_id, Document.tenant_id == tenant_id))
        res = await self.db.execute(doc_stmt)
        doc = res.scalar_one_or_none()
        if doc:
            doc.status = "COMPLETED"
            doc.total_chunks = len(db_chunks)

        await self.db.commit()

    async def search_similar_chunks(
        self,
        tenant_id: str,
        query_vector: List[float],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        核心向量相似度检索 (Multi-Tenant Scoped Vector Search)
        严格保证只会检索当前 tenant_id 下的知识，绝不跨租户越权！
        """
        if db_session.IS_POSTGRES:
            # PostgreSQL pgvector 原生余弦距离检索
            # <=> 操作符：cosine distance = 1 - cosine_similarity
            distance_col = DocumentChunk.embedding.cosine_distance(query_vector)
            stmt = (
                select(DocumentChunk, distance_col.label("distance"), Document.filename)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.tenant_id == tenant_id)
                .order_by("distance")
                .limit(top_k)
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            results = []
            for chunk, distance, filename in rows:
                similarity = 1.0 - float(distance) if distance is not None else 0.0
                results.append({
                    "id": f"chunk_{chunk.id}",
                    "document_id": chunk.document_id,
                    "source": filename,
                    "text": chunk.content,
                    "meta_info": chunk.meta_info,
                    "score": round(similarity, 4)
                })
            return results

        else:
            # 本地 SQLite 开发 fallback：基于内存向量计算
            stmt = (
                select(DocumentChunk, Document.filename)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(DocumentChunk.tenant_id == tenant_id)
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            scored = []
            q_vec = np.array(query_vector)
            q_norm = np.linalg.norm(q_vec)

            for chunk, filename in rows:
                if chunk.embedding:
                    c_vec = np.array(chunk.embedding)
                    c_norm = np.linalg.norm(c_vec)
                    sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm)) if (q_norm and c_norm) else 0.0
                else:
                    sim = 0.0
                scored.append((sim, chunk, filename))

            scored.sort(key=lambda x: x[0], reverse=True)
            results = []
            for sim, chunk, filename in scored[:top_k]:
                results.append({
                    "id": f"chunk_{chunk.id}",
                    "document_id": chunk.document_id,
                    "source": filename,
                    "text": chunk.content,
                    "meta_info": chunk.meta_info,
                    "score": round(sim, 4)
                })
            return results
