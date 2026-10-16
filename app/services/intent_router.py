import re
from enum import Enum
from typing import Dict, Any

class IntentType(str, Enum):
    CHITCHAT = "CHITCHAT"              # General greetings / 闲聊通道 (0 vector search)
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"  # Enterprise policy RAG / 知识库问答
    ACTION_TOOL = "ACTION_TOOL"        # Workflow actions / 业务办理工单

class IntentRouter:
    """
    Intelligent Intent Router (Inspired by ruflo Agentic Workflows)
    Pre-filters queries to eliminate redundant database IO and vector operations.
    """

    # 常见问候与闲聊正则 (Bilingual: English + Chinese)
    CHITCHAT_PATTERNS = [
        r"(hello|hi\b|hey\b|good\s+morning|good\s+afternoon|good\s+evening|greetings|你好|您好|早上好|下午好|晚上好|嗨)",
        r"(who\s+are\s+you|what\s+can\s+you\s+do|introduce\s+yourself|你是谁|你叫什么|介绍.*自己|你能做什么|你可以做什么)",
        r"(thank\s+you|thanks|thx|bye|goodbye|谢谢|感谢|再见|拜拜)"
    ]

    # 业务操作与动作指令正则 (Bilingual: English + Chinese)
    ACTION_PATTERNS = [
        r"(help\s+me|apply|submit|request|create|initiate|帮我|我要|提交|发起|申请).*(leave|pto|vacation|reimburse|expense|approval|ticket|请假|休假|报销|补卡|审批)",
        r"(reset|change|modify|重置|修改).*(password|wifi|credential|access|密码|wifi|权限)",
        r"(check|track|view|query|查询|查看).*(status|progress|payslip|salary|ticket|审批进度|报销进度|工资条|工单)"
    ]

    @classmethod
    def route(cls, query: str) -> Dict[str, Any]:
        cleaned_query = query.strip()

        # 1. 匹配闲聊
        for pattern in cls.CHITCHAT_PATTERNS:
            if re.search(pattern, cleaned_query, re.IGNORECASE):
                return {
                    "intent": IntentType.CHITCHAT,
                    "confidence": 0.96,
                    "reason": "Direct Chat Channel / 命中常规会话通道"
                }

        # 2. 匹配业务动作办理
        for pattern in cls.ACTION_PATTERNS:
            if re.search(pattern, cleaned_query, re.IGNORECASE):
                return {
                    "intent": IntentType.ACTION_TOOL,
                    "confidence": 0.94,
                    "reason": "Workflow Action Dispatcher / 识别为业务工单指令"
                }

        # 3. 默认进入核心 RAG 知识检索
        return {
            "intent": IntentType.KNOWLEDGE_QUERY,
            "confidence": 0.90,
            "reason": "Enterprise Knowledge Search / 规章制度检索"
        }
