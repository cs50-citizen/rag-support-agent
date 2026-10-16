import re
from typing import List, Dict, Any, Tuple

class ContextCompressor:
    """
    Context Compressor & Noise Reducer (Inspired by context-mode & caveman)
    Prunes redundant prose, disclaimers, and formatting noise to optimize prompt tokens.
    """

    @classmethod
    def compress(cls, query: str, context_chunks: List[str]) -> Tuple[str, Dict[str, Any]]:
        """
        Compresses retrieved context chunks.
        Returns: (compressed_context, compression_statistics)
        """
        raw_combined = "\n\n".join(context_chunks)
        orig_len = len(raw_combined)

        if not raw_combined.strip():
            return "", {"original_chars": 0, "compressed_chars": 0, "saved_pct": "0.0%"}

        # 1. 提取英文核心词
        stop_words_en = {"the", "is", "are", "in", "at", "what", "how", "much", "many", "can", "for", "of", "to", "a", "an", "i", "my", "you"}
        en_words = {w.lower() for w in re.findall(r"\b[a-zA-Z]{3,}\b", query) if w.lower() not in stop_words_en}

        # 2. 提取中文 2-gram 关键词
        cleaned_zh = re.sub(r"[^\u4e00-\u9fa5]", "", query)
        stop_subwords = {"请问", "怎么", "如何", "多少", "什么", "可以", "以及", "一天", "最多", "如果"}
        zh_terms = set()
        for i in range(len(cleaned_zh) - 1):
            sub = cleaned_zh[i:i+2]
            if sub not in stop_subwords:
                zh_terms.add(sub)

        query_terms = en_words.union(zh_terms)
        compressed_snippets = []

        for chunk in context_chunks:
            # 按标点或换行分句 (Support EN & ZH sentence delimiters)
            sentences = [s.strip() for s in re.split(r"(?<=[。！？\.\?!])\s*|\n+", chunk) if s.strip()]
            matched_sentences = []
            
            for sent in sentences:
                sent_lower = sent.lower()
                # 计算句子与问题的关联词命中数
                hit_count = sum(1 for term in query_terms if term in sent_lower)
                if hit_count > 0:
                    matched_sentences.append(sent)

            if matched_sentences:
                # 仅保留高密度证据句
                compressed_snippets.append("\n".join(matched_sentences))
            else:
                # 兜底保留
                fallback_sents = [s for s in sentences if re.search(r"(\d+|RMB|\$|prohibit|must|policy|禁止|必须|规定)", s, re.IGNORECASE)]
                if fallback_sents:
                    compressed_snippets.append("\n".join(fallback_sents[:2]))
                else:
                    compressed_snippets.append(chunk[:120].strip() + "...")

        compressed_text = "\n\n---\n\n".join(compressed_snippets)
        comp_len = len(compressed_text)

        saved_chars = max(0, orig_len - comp_len)
        saved_pct = (saved_chars / orig_len * 100) if orig_len > 0 else 0.0

        stats = {
            "original_chars": orig_len,
            "compressed_chars": comp_len,
            "saved_chars": saved_chars,
            "saved_pct": f"{saved_pct:.1f}%"
        }

        return compressed_text, stats
