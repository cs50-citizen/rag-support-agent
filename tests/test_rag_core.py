import pytest
from app.services.intent_router import IntentRouter, IntentType
from app.services.context_compressor import ContextCompressor

def test_intent_router_chitchat():
    res = IntentRouter.route("Hello there!")
    assert res["intent"] == IntentType.CHITCHAT

    res2 = IntentRouter.route("Who are you and what can you do?")
    assert res2["intent"] == IntentType.CHITCHAT

    res3 = IntentRouter.route("你好呀！")
    assert res3["intent"] == IntentType.CHITCHAT

def test_intent_router_action_tool():
    res = IntentRouter.route("Help me submit an annual leave approval request for next Wednesday")
    assert res["intent"] == IntentType.ACTION_TOOL

    res2 = IntentRouter.route("Please submit travel reimbursement expense report")
    assert res2["intent"] == IntentType.ACTION_TOOL

    res3 = IntentRouter.route("帮我申请下周三的带薪年假审批")
    assert res3["intent"] == IntentType.ACTION_TOOL

def test_intent_router_knowledge_query():
    res = IntentRouter.route("What is the daily meal allowance for business trips to Tier-1 cities?")
    assert res["intent"] == IntentType.KNOWLEDGE_QUERY

def test_context_compressor_pruning():
    query = "What is the daily meal allowance for business trips to Tier-1 cities?"
    raw_chunks = [
        "Chapter 1: Purpose & General Provisions. This corporate policy is established to govern company-wide travel.\n"
        "Chapter 2: Daily Meal Allowance. Employees traveling to Tier-1 metropolitan areas are entitled to a daily meal subsidy of up to $25 USD.\n"
        "Chapter 3: Train Standards. High-speed rail second-class is preferred for domestic journeys under 5 hours."
    ]
    compressed_text, stats = ContextCompressor.compress(query, raw_chunks)
    assert "$25 USD" in compressed_text
    assert stats["original_chars"] > stats["compressed_chars"]
    saved_ratio = float(stats["saved_pct"].replace("%", ""))
    assert saved_ratio > 0.0
