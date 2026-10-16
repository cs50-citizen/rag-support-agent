import re
from enum import Enum
from typing import Dict, Any

class IntentType(str, Enum):
    CHITCHAT = "CHITCHAT"                # General greetings & chitchat (0 DB queries)
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"  # Enterprise policy vector search
    ACTION_TOOL = "ACTION_TOOL"          # Operational workflow directives & tickets

class IntentRouter:
    """
    Intelligent Intent Router (Inspired by ruflo Agentic Workflows)
    Pre-filters queries to eliminate redundant database IO and vector operations.
    """

    CHITCHAT_PATTERNS = [
        r"(hello|hi\b|hey\b|good\s+morning|good\s+afternoon|good\s+evening|greetings|howdy|sup\b|你好|您好|嗨)",
        r"(who\s+are\s+you|what\s+can\s+you\s+do|introduce\s+yourself|你是谁|你叫什么|你能做什么)",
        r"(thank\s+you|thanks|thx|bye|goodbye|see\s+you|cheers|谢谢|再见)"
    ]

    ACTION_PATTERNS = [
        r"(help\s+me|apply|submit|request|create|initiate|file|帮我|我要|提交|申请).*(leave|pto|vacation|reimburse|expense|approval|ticket|请假|休假|报销|审批)",
        r"(reset|change|modify|rotate|重置|修改).*(password|wifi|credential|access|token|密码|权限)",
        r"(check|track|view|query|inspect|查询|查看).*(status|progress|payslip|salary|ticket|audit|进度|工单)"
    ]

    @classmethod
    def route(cls, query: str) -> Dict[str, Any]:
        cleaned_query = query.strip()

        # 1. Chitchat Fast-path
        for pattern in cls.CHITCHAT_PATTERNS:
            if re.search(pattern, cleaned_query, re.IGNORECASE):
                return {
                    "intent": IntentType.CHITCHAT,
                    "confidence": 0.98,
                    "reason": "Direct Chitchat Channel (0 DB vector operations)"
                }

        # 2. Workflow Action Tool Dispatch
        for pattern in cls.ACTION_PATTERNS:
            if re.search(pattern, cleaned_query, re.IGNORECASE):
                return {
                    "intent": IntentType.ACTION_TOOL,
                    "confidence": 0.95,
                    "reason": "Workflow Action Tool Dispatcher"
                }

        # 3. Enterprise Knowledge Retrieval (Default RAG)
        return {
            "intent": IntentType.KNOWLEDGE_QUERY,
            "confidence": 0.92,
            "reason": "Enterprise Knowledge Vector Search"
        }
