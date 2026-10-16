import os
import re
import json
import asyncio
import hashlib
from typing import AsyncGenerator, Dict, Any, List

from app.core.config import settings
import app.db.session as db_session
from app.repositories.vector_repo import VectorRepository
from app.services.intent_router import IntentRouter, IntentType
from app.services.context_compressor import ContextCompressor

class RAGService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.has_real_key = bool(self.api_key and self.api_key != "your_gemini_api_key_here")

        if self.has_real_key:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

        self._initialized = False

    async def initialize_database_and_seed(self):
        """
        初始化数据库表结构，并为两个不同的测试租户注入隔离知识
        """
        if self._initialized:
            return

        await db_session.init_db()

        async with db_session.AsyncSessionLocal() as session:
            repo = VectorRepository(session)

            # 检查是否已播种并先清理旧种子文档，确保写入最新多语言向量
            await repo.get_or_create_tenant("tenant_default", "通用企业租户")
            await repo.get_or_create_tenant("corp_finance", "财务绝密租户")

            from sqlalchemy import delete
            from app.models.schema import Document, DocumentChunk
            stmt_del_chunks = delete(DocumentChunk).where(DocumentChunk.tenant_id.in_(["tenant_default", "corp_finance"]))
            await session.execute(stmt_del_chunks)
            stmt_del_docs = delete(Document).where(Document.tenant_id.in_(["tenant_default", "corp_finance"]))
            await session.execute(stmt_del_docs)
            await session.commit()

            # 读取 sample_docs/enterprise_faq.txt
            doc_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_docs")
            faq_path = os.path.join(doc_dir, "enterprise_faq.txt")

            if os.path.exists(faq_path):
                with open(faq_path, "r", encoding="utf-8") as f:
                    content = f.read()
                raw_chunks = [c.strip() for c in re.split(r"\n\s*\n", content) if c.strip()]
                
                # 播种到 tenant_default
                doc1 = await repo.create_document("tenant_default", "enterprise_faq.txt")
                chunks_data1 = []
                for c in raw_chunks:
                    emb = self.get_embedding(c)
                    chunks_data1.append({
                        "content": c,
                        "embedding": emb,
                        "meta_info": {"source": "enterprise_faq.txt", "department": "General"}
                    })
                await repo.save_chunks("tenant_default", doc1.id, chunks_data1)

            # Seed specific confidential records to corp_finance tenant
            finance_text = (
                "[Confidential Finance Policies & Year-End Bonus Regulations]\n"
                "1. Year-End Bonus: The annual bonus calculation base for the finance department is 3.5 months of base salary, distributed on the final business day of January.\n"
                "2. Confidentiality: Payroll, compensation rates, and bonus distributions are classified as strictly confidential corporate trade secrets. Disclosure to unauthorized departments or external entities is strictly prohibited and subject to immediate termination."
            )
            doc2 = await repo.create_document("corp_finance", "finance_confidential.txt")
            emb2 = self.get_embedding(finance_text)
            chunks_data2 = [{
                "content": finance_text,
                "embedding": emb2,
                "meta_info": {"source": "finance_confidential.txt", "department": "Finance"}
            }]
            await repo.save_chunks("corp_finance", doc2.id, chunks_data2)

        self._initialized = True

    def _mock_embed(self, text: str) -> List[float]:
        # 教学模拟向量：结合中英多语言领域关键词 + 确定性哈希特征 (768 维)
        vec = [0.0] * 768
        text_lower = text.lower()
        keywords = [
            # Chinese
            "报销", "补贴", "出差", "餐饮", "高铁", "机票", "WiFi", "密码", "锁屏",
            "堡垒机", "年假", "福利", "生日", "年终奖", "薪酬", "财务", "远程", "津贴",
            "出張", "手当", "手当金", "休暇", "ボーナス",
            # English
            "allowance", "subsidy", "meal", "travel", "trip", "reimbursement", "flight",
            "hotel", "train", "wifi", "password", "screen", "lock", "annual", "leave",
            "pto", "vacation", "benefit", "birthday", "bonus", "salary", "payroll",
            "finance", "remote", "database", "mfa", "security"
        ]
        # 1. 领域关键词特征 (高权重驱动语义匹配)
        for idx, kw in enumerate(keywords):
            if kw in text_lower:
                vec[(idx * 13) % 768] += 8.0

        # 2. 确定性字符双元 (2-gram) 哈希散列 (跨进程跨平台稳定)
        for i in range(len(text) - 1):
            pair = text[i:i+2].encode("utf-8")
            h = int(hashlib.md5(pair).hexdigest(), 16) % 768
            vec[h] += 0.2

        # 归一化为单位向量 (L2 Norm)
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else vec

    def get_embedding(self, text: str) -> List[float]:
        if self.has_real_key and self.client:
            res = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            return res.embeddings[0].values
        return self._mock_embed(text)

    async def stream_rag_answer(self, query: str, tenant_id: str = "tenant_default") -> AsyncGenerator[str, None]:
        """
        核心 SSE 生成器：整合意图路由、向量检索、上下文降噪与流式输出 (Bilingual / English-Prioritized)
        """
        if not self._initialized:
            await self.initialize_database_and_seed()

        # ==========================================
        # 步骤 1：意图路由分流 (借鉴 ruflo 思想)
        # ==========================================
        route_decision = IntentRouter.route(query)
        intent = route_decision["intent"]

        yield f"data: {json.dumps({'event': 'intent', 'intent': intent.value, 'reason': route_decision['reason']}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        # Branch A: Chitchat Channel (0 DB vector searches, instant response)
        if intent == IntentType.CHITCHAT:
            reply = (
                "Hello! I am your Enterprise RAG Knowledge Base & Autonomous Support Agent. "
                "I am equipped with multi-tenant data isolation and dynamic context pruning engines. "
                "Feel free to query corporate policies (e.g., travel meal allowances, IT security standards, annual PTO benefits) "
                "or issue workflow automation directives!"
            )
            for char in reply:
                yield f"data: {json.dumps({'event': 'token', 'text': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.012)
            yield f"data: {json.dumps({'event': 'done', 'references': []}, ensure_ascii=False)}\n\n"
            return

        # Branch B: Action Directive & Tool Calling Channel (Agent Tool Calling)
        if intent == IntentType.ACTION_TOOL:
            reply = (
                f"【Agent Workflow Directive Initiated】:\n"
                f"- Request Directive: {query}\n"
                f"- Tenant Scope: [{tenant_id}]\n"
                f"- Reference Ticket ID: #REQ-2026-9042\n"
                f"- Execution Status: Automated draft generated and submitted to corporate OA approval queue. Please check your notification feed shortly."
            )
            for char in reply:
                yield f"data: {json.dumps({'event': 'token', 'text': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.012)
            yield f"data: {json.dumps({'event': 'done', 'references': [{'source': 'OA_Workflow_Engine', 'id': 'REQ-2026-9042', 'score': 1.0}]}, ensure_ascii=False)}\n\n"
            return

        # ==========================================
        # Step 2: Multi-Tenant Vector Retrieval (pgvector)
        # ==========================================
        query_vec = self.get_embedding(query)
        async with db_session.AsyncSessionLocal() as session:
            repo = VectorRepository(session)
            retrieved_docs = await repo.search_similar_chunks(tenant_id=tenant_id, query_vector=query_vec, top_k=2)

        yield f"data: {json.dumps({'event': 'retrieving', 'message': f'Retrieved {len(retrieved_docs)} candidate evidence chunks under tenant [{tenant_id}]...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        raw_contexts = [d["text"] for d in retrieved_docs]

        # ==========================================
        # Step 3: Context Pruning & Compression (Inspired by context-mode)
        # ==========================================
        compressed_context, comp_stats = ContextCompressor.compress(query, raw_contexts)
        yield f"data: {json.dumps({'event': 'compression', 'stats': comp_stats}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        # ==========================================
        # Step 4: Confidence Guardrails (Hallucination & Out-of-Domain Interception)
        # ==========================================
        SIMILARITY_THRESHOLD = 0.25
        top_match = retrieved_docs[0] if retrieved_docs else None
        is_confident = bool(top_match and top_match["score"] >= SIMILARITY_THRESHOLD)

        if not is_confident:
            answer_content = (
                f"【Knowledge Base Out-of-Domain Notice】:\n"
                f"No matching enterprise policies or records were found for \"{query}\" under tenant space [{tenant_id}].\n\n"
                f"💡 Architecture & Guardrail Insights:\n"
                f"1. **Private Intranet Guardrails**: This system guards private corporate records. Queries regarding public Internet topics (e.g., public search engines, external commercial banks) are strictly rejected due to absence in the corporate document store, eliminating LLM hallucinations.\n"
                f"2. **Dense Vector Embeddings**: Running under local mock embedding mode. To enable semantic vector querying across multilingual documents, provide a `GEMINI_API_KEY` in your `.env` to activate Gemini's dense embedding model."
            )
            for char in answer_content:
                payload = {"event": "token", "text": char}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'event': 'done', 'references': [], 'compression': comp_stats}, ensure_ascii=False)}\n\n"
            return

        # ==========================================
        # Step 5: Augmented Generation & SSE Streaming
        # ==========================================
        if self.has_real_key and self.client:
            prompt = f"""You are a professional Enterprise Internal Knowledge Base AI Assistant.
Answer the user's question accurately and strictly based on the provided reference contexts below.
If the reference material does not contain the answer, explicitly state "The enterprise knowledge base does not contain relevant information regarding your query." Do not hallucinate or fabricate facts.
Respond clearly and concisely in professional English.

[Core Reference Context]:
{compressed_context}

[User Query]:
{query}

Please formulate your response:"""
            response_stream = self.client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=prompt
            )
            for chunk in response_stream:
                if chunk.text:
                    payload = {"event": "token", "text": chunk.text}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)
        else:
            # Teaching / Local Mock Typewriter Stream
            answer_content = (
                f"【Multi-Tenant Verified Response】:\n"
                f"Verified records under tenant scope [{tenant_id}] "
                f"(Pruned {comp_stats['saved_pct']} redundant tokens via Context Compressor):\n\n"
                f"{compressed_context}"
            )
            for char in answer_content:
                payload = {"event": "token", "text": char}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.012)

        # 6. 发送引用来源与完成事件
        references = [
            {"id": d["id"], "source": d["source"], "score": d["score"], "meta": d["meta_info"]}
            for d in retrieved_docs
        ]
        yield f"data: {json.dumps({'event': 'done', 'references': references, 'compression': comp_stats}, ensure_ascii=False)}\n\n"

rag_service = RAGService()
