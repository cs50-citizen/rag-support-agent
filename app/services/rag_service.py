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

            # 播种特定私有数据到 corp_finance 租户 (Bilingual English-first)
            finance_text = (
                "[Confidential Finance Policies & Year-End Bonus Regulations / 财务机密制度与年终奖细则]\n"
                "1. Year-End Bonus: Finance department bonus calculation base is 3.5 months base salary, disbursed on the last business day of January. "
                "(财务部门年终奖计算基数为 3.5 个月全薪，每年 1 月最后一个工作日发放。)\n"
                "2. Confidentiality: Payroll and bonus records are strictly confidential trade secrets. Disclosure to unauthorized departments is strictly prohibited. "
                "(薪酬属于绝密级商业机密，严禁向其他任何部门泄露，违者解除劳动合同。)"
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

        # 分支 A：普通闲聊通道（0 次向量库检索，毫秒级响应）
        if intent == IntentType.CHITCHAT:
            reply = (
                "Hello! I am your Enterprise RAG Knowledge Base & Autonomous Support Agent. "
                "You can query corporate policies (e.g., travel meal allowance, IT security regulations, annual PTO) "
                "or request workflow task assistance!\n\n"
                "(您好！我是企业智能知识库与业务支持 Agent，已为您挂载多租户数据隔离空间，请随时提问！)"
            )
            for char in reply:
                yield f"data: {json.dumps({'event': 'token', 'text': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.012)
            yield f"data: {json.dumps({'event': 'done', 'references': []}, ensure_ascii=False)}\n\n"
            return

        # 分支 B：业务办理与动作指令通道 (Agent Tool Calling)
        if intent == IntentType.ACTION_TOOL:
            reply = (
                f"【Agent Workflow Ticket Initiated / 业务工单已受理】:\n"
                f"- Request Directive / 操作指令: {query}\n"
                f"- Tenant Scope / 归属租户空间: [{tenant_id}]\n"
                f"- Ticket Reference / 系统工单号: #REQ-2026-9042\n"
                f"- Execution Status / 当前状态: Automated draft generated and submitted to corporate OA approval queue. "
                f"(已自动生成草案单并推送至 OA 审批待办队列，请稍后查收通知！)"
            )
            for char in reply:
                yield f"data: {json.dumps({'event': 'token', 'text': char}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.012)
            yield f"data: {json.dumps({'event': 'done', 'references': [{'source': 'OA_Workflow_Engine', 'id': 'REQ-2026-9042', 'score': 1.0}]}, ensure_ascii=False)}\n\n"
            return

        # ==========================================
        # 步骤 2：知识库多租户向量检索 (pgvector)
        # ==========================================
        query_vec = self.get_embedding(query)
        async with db_session.AsyncSessionLocal() as session:
            repo = VectorRepository(session)
            retrieved_docs = await repo.search_similar_chunks(tenant_id=tenant_id, query_vector=query_vec, top_k=2)

        yield f"data: {json.dumps({'event': 'retrieving', 'message': f'Retrieved {len(retrieved_docs)} candidate evidence chunks under tenant [{tenant_id}] (在租户空间检索到 {len(retrieved_docs)} 条候选证据)...'}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        raw_contexts = [d["text"] for d in retrieved_docs]

        # ==========================================
        # 步骤 3：上下文降噪与 Token 压缩 (借鉴 context-mode)
        # ==========================================
        compressed_context, comp_stats = ContextCompressor.compress(query, raw_contexts)
        yield f"data: {json.dumps({'event': 'compression', 'stats': comp_stats}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        # ==========================================
        # 步骤 4：置信度阈值判定 (防幻觉与外网无关问题拦截)
        # ==========================================
        SIMILARITY_THRESHOLD = 0.25
        top_match = retrieved_docs[0] if retrieved_docs else None
        is_confident = bool(top_match and top_match["score"] >= SIMILARITY_THRESHOLD)

        if not is_confident:
            answer_content = (
                f"【Knowledge Base Notice / 知识库未命中提示】:\n"
                f"No matching enterprise policies or records were found for \"{query}\" under tenant space [{tenant_id}]. "
                f"(在您的租户空间 [{tenant_id}] 下未检索到与“{query}”相关的企业内部规章制度。)\n\n"
                f"💡 Architecture & Guardrail Insights (架构说明):\n"
                f"1. **Private Intranet Guardrails (企业内网边界)**: This system guards private corporate records. "
                f"Queries regarding public Internet topics (e.g., \"Baidu\", \"Bank of China\") are strictly rejected due to absence in the corporate document store, eliminating LLM hallucinations (杜绝大模型无中生有与虚构假事实).\n"
                f"2. **Cross-Lingual Multilingual Retrieval (跨语言向量召回)**: Running under local mock embedding mode. "
                f"To query English/Chinese documents across Japanese/English/Chinese, provide a `GEMINI_API_KEY` in your `.env` file to activate Gemini's dense multilingual embedding model."
            )
            for char in answer_content:
                payload = {"event": "token", "text": char}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            yield f"data: {json.dumps({'event': 'done', 'references': [], 'compression': comp_stats}, ensure_ascii=False)}\n\n"
            return

        # ==========================================
        # 步骤 5：增强生成与流式打字机输出
        # ==========================================
        if self.has_real_key and self.client:
            prompt = f"""You are a professional Enterprise Internal Knowledge Base AI Assistant.
Answer the user's question accurately and strictly based on the provided reference contexts below.
If the reference material does not contain the answer, explicitly state "The enterprise knowledge base does not contain relevant information / 知识库中未找到相关规定". Do not hallucinate or make up information.
Respond primarily in English, followed by a Chinese translation or summary if helpful.

[Core Reference Context / 核心证据]:
{compressed_context}

[User Query / 用户问题]:
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
            # 教学模拟打字机流式输出
            answer_content = (
                f"【Multi-Tenant Verified Response / 多租户与降噪流式回答】:\n"
                f"Verified records under tenant scope [{tenant_id}] "
                f"(Context pruning pruned {comp_stats['saved_pct']} redundant tokens / 上下文精简已裁剪 {comp_stats['saved_pct']}):\n\n"
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
