"""
Enterprise RAG Knowledge Base - Milestone 1: 极简 RAG 原型验证
------------------------------------------------------------------
本脚本用最清晰直观的方式演示 RAG (检索增强生成) 的完整闭环四部曲：
1. Document Parsing & Chunking (文档加载与切分)
2. Vector Embedding (语义向量化)
3. Similarity Retrieval (基于余弦相似度的相关知识检索)
4. Augmented Generation (注入检索上下文，大模型生成回答)
"""

import os
import re
import numpy as np
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# 步骤 1：文档解析与语义切块 (Chunking)
# ==========================================
def load_and_chunk_document(file_path: str) -> list[str]:
    """
    读取企业文档，并按段落/规则切块。
    在工业界中，大文档不能整篇塞给大模型，必须切成适合搜索的小片段（Chunks）。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 简单策略：按空行或小标题切分
    raw_chunks = re.split(r"\n\s*\n", text)
    chunks = [c.strip() for c in raw_chunks if c.strip()]
    return chunks


# ==========================================
# 步骤 2：向量化 (Vector Embedding)
# ==========================================
def get_embedding(client, text: str) -> list[float]:
    """
    将一段自然语言文本转换成一个浮点数数组（向量）。
    语义相近的句子，其向量在多维空间中的几何距离也会非常相近。
    """
    response = client.models.embed_content(
        model="text-embedding-004",
        contents=text
    )
    # 取出第一个嵌入向量
    return response.embeddings[0].values


# ==========================================
# 步骤 3：相似度检索 (Similarity Retrieval)
# ==========================================
def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """
    余弦相似度计算公式：(A · B) / (||A|| * ||B||)
    结果范围 [-1, 1]，越接近 1 说明两句话在语义上越相似。
    这也是后续 PostgreSQL pgvector 中 <=> 距离操作符的核心数学原理。
    """
    a = np.array(v1)
    b = np.array(v2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_relevant_chunks(client, query: str, chunks: list[str], chunk_vectors: list[list[float]], top_k: int = 2):
    """
    计算用户提问与知识库中所有切片的相似度，返回得分最高的前 top_k 个片段。
    """
    query_vector = get_embedding(client, query)
    scores = []
    for idx, doc_vector in enumerate(chunk_vectors):
        score = cosine_similarity(query_vector, doc_vector)
        scores.append((score, chunks[idx]))

    # 按相似度降序排序
    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[:top_k]


# ==========================================
# 步骤 4：增强生成 (Augmented Generation)
# ==========================================
def answer_with_rag(client, query: str, context_chunks: list[str]) -> str:
    """
    将检索出的相关资料拼接到 Prompt 中，要求大模型仅根据参考资料严谨作答。
    """
    context_text = "\n\n---\n\n".join(context_chunks)

    prompt = f"""你是一名严谨的企业内部知识库智能助理。请严格根据以下给出的参考资料回答用户问题。
如果参考资料中没有提及，请直接说“知识库中未找到相关规定”，切勿编造假信息。

【参考资料】：
{context_text}

【用户问题】：
{query}

请作答："""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text


def run_mock_simulation():
    """
    教学模拟模式：无需 API Key，用纯 Python 模拟 RAG 全流程，直观展示原理！
    """
    print("\n💡 [教学模拟模式已启动] 正在为您演示 RAG 核心计算原理...")
    doc_path = os.path.join(os.path.dirname(__file__), "sample_docs", "enterprise_faq.txt")
    chunks = load_and_chunk_document(doc_path)
    print(f"📂 1. 读取企业内部文档并切块，共生成 {len(chunks)} 个切片。")

    # 简单词频特征作为教学用模拟向量 (Bag of Words / Mock Embedding)
    keywords = ["报销", "补贴", "高铁", "WiFi", "锁屏", "堡垒机", "年假", "福利", "生日"]
    
    def mock_embed(text: str) -> list[float]:
        # 统计关键词频率 + 字符数哈希模拟多维向量
        return [float(text.count(k) * 5 + 0.1) for k in keywords]

    chunk_vectors = [mock_embed(c) for c in chunks]
    print(f"🧠 2. 模拟向量化完成 (每个切片提取 {len(keywords)} 维语义特征)")

    query = "我如果去上海出差，一天最多能报销多少饭钱？"
    print(f"\n❓ 用户提问: {query}")
    query_vec = mock_embed(query)
    
    # 计算余弦相似度
    scores = [(cosine_similarity(query_vec, v), chunks[i]) for i, v in enumerate(chunk_vectors)]
    scores.sort(key=lambda x: x[0], reverse=True)
    best_score, best_chunk = scores[0]

    print(f"🔍 3. 相似度匹配结果 (最高相似度得分: {best_score:.4f}):")
    print(f"   匹配到规则片段:\n   \"{best_chunk}\"")
    print("\n🤖 4. 大模型注入资料并回答:")
    print("💡 [模拟回答]: 根据公司差旅与报销制度，国内一线城市（如上海）出差每日餐饮补贴最高可报销 150 元，无需发票但需提供出差打卡记录。")
    print("\n" + "=" * 60)
    print("🎉 恭喜！您已经亲眼见证了 RAG 的核心底层逻辑。")
    print("👉 下一步：获取真实的 Gemini API Key 填入 .env，即可体验真实大模型推理！")

# ==========================================
# 主流程演示
# ==========================================
def main():
    print("=" * 60)
    print("🚀 欢迎进入企业级 RAG 知识库演示 (Milestone 1)")
    print("=" * 60)

    # 检查 API Key
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("\n⚠️  提示：未检测到真实的 GEMINI_API_KEY。")
        print("您现在有两个选择：")
        print("1. 免费申请 Gemini API Key: https://aistudio.google.com/apikey 填入 .env")
        print("2. 立即运行内置的【教学模拟模式】，零配置感受 RAG 完整检索过程！")
        run_mock_simulation()
        return

    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)

    # 1. 加载并切分文档
    doc_path = os.path.join(os.path.dirname(__file__), "sample_docs", "enterprise_faq.txt")
    print(f"\n📂 1. 读取企业内部文档: {doc_path}")
    chunks = load_and_chunk_document(doc_path)
    print(f"   已成功切分为 {len(chunks)} 个知识切片(Chunks)。")

    # 2. 向量化知识库
    print("\n🧠 2. 正在调用 text-embedding-004 对所有切片进行向量化...")
    chunk_vectors = []
    for i, c in enumerate(chunks, 1):
        print(f"   - 正在向量化第 {i}/{len(chunks)} 片段...")
        vec = get_embedding(client, c)
        chunk_vectors.append(vec)
    print(f"   向量化完成！每个向量维度: {len(chunk_vectors[0])} 维。")

    # 3. 提问与检索
    questions = [
        "我如果去上海出差，一天最多能报销多少饭钱？",
        "我离开座位忘了锁电脑，有规定要求几分钟内必须锁屏吗？",
        "公司年假是怎么算的？刚入职满一年的员工有几天？"
    ]

    for q in questions:
        print("\n" + "=" * 60)
        print(f"❓ 用户提问: {q}")

        # 检索最相关的知识片段
        relevant = search_relevant_chunks(client, q, chunks, chunk_vectors, top_k=1)
        score, best_chunk = relevant[0]
        print(f"🔍 检索到的最匹配知识 (相似度: {score:.4f}):")
        print(f"   \"{best_chunk[:100]}...\"")

        # 结合知识回答
        print("🤖 大模型生成回答中...")
        answer = answer_with_rag(client, q, [best_chunk])
        print("💡 回答结果:")
        print(answer)

if __name__ == "__main__":
    main()
