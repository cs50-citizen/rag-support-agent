import pytest
from app.services.intent_router import IntentRouter, IntentType
from app.services.context_compressor import ContextCompressor

def test_intent_router_chitchat():
    res = IntentRouter.route("你好呀！")
    assert res["intent"] == IntentType.CHITCHAT

    res2 = IntentRouter.route("你是谁？能做什么？")
    assert res2["intent"] == IntentType.CHITCHAT

def test_intent_router_action_tool():
    res = IntentRouter.route("帮我申请下周三的带薪年假审批")
    assert res["intent"] == IntentType.ACTION_TOOL

    res2 = IntentRouter.route("请帮我提交差旅报销单据")
    assert res2["intent"] == IntentType.ACTION_TOOL

def test_intent_router_knowledge_query():
    res = IntentRouter.route("公司对于一线城市出差餐饮补贴的具体标准是多少？")
    assert res["intent"] == IntentType.KNOWLEDGE_QUERY

def test_context_compressor_pruning():
    query = "上海餐饮补贴多少钱？"
    raw_chunks = [
        "第一章 总则与目的：为了规范差旅报销，特制订本制度。本制度自2026年起生效，由总经办监督执行。\n"
        "第二章 餐饮补贴：国内一线城市出差每人每天最高可报销 150 元，二三线城市最高报销 100 元。\n"
        "第三章 乘车规范：单程高铁在5小时内应优先选择二等座。"
    ]
    compressed_text, stats = ContextCompressor.compress(query, raw_chunks)
    assert "150 元" in compressed_text
    assert stats["original_chars"] > stats["compressed_chars"]
    saved_ratio = float(stats["saved_pct"].replace("%", ""))
    assert saved_ratio > 0.0

