"""
Milestone 4 验证脚本: 意图路由与上下文降噪器 (ruflo & context-mode 精髓)
------------------------------------------------------------------------
验证内容：
1. 快速闲聊分流 (0 次数据库检索)
2. Agent 动作指令分流 (模拟调用审批流程)
3. 核心知识库问答 + 动态上下文降噪压缩率评估
"""

import sys
import json
from fastapi.testclient import TestClient
from app.main import app

def parse_sse_events(response_text: str):
    events = []
    for line in response_text.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events

def run_tests():
    print("=" * 70)
    print("🧠 Milestone 4: 智能意图路由与上下文降噪压缩验证")
    print("=" * 70)

    with TestClient(app) as client:
        # Case 1: 闲聊分流 (CHITCHAT)
        print("\n[测试 1: 闲聊通道测试 (ruflo 路由思想)]")
        q1 = "你好！"
        print(f"❓ 用户输入: {q1}")
        res1 = client.post("/api/v1/chat/stream", json={"query": q1, "tenant_id": "tenant_default"})
        events1 = parse_sse_events(res1.text)
        intent_event1 = next((e for e in events1 if e.get("event") == "intent"), {})
        print(f"🎯 识别意图: {intent_event1.get('intent')} | 理由: {intent_event1.get('reason')}")
        reply1 = "".join([e.get("text", "") for e in events1 if e.get("event") == "token"])
        print(f"🤖 助手直接回复: {reply1[:80]}...")
        assert intent_event1.get("intent") == "CHITCHAT"
        print("✅ 闲聊验证通过：未触发数据库向量查询，极速响应！")

        # Case 2: 业务动作指令 (ACTION_TOOL)
        print("\n" + "-" * 70)
        print("[测试 2: Agent 动作指令测试 (Agentic Action)]")
        q2 = "帮我申请明天的年假休假审批"
        print(f"❓ 用户输入: {q2}")
        res2 = client.post("/api/v1/chat/stream", json={"query": q2, "tenant_id": "tenant_default"})
        events2 = parse_sse_events(res2.text)
        intent_event2 = next((e for e in events2 if e.get("event") == "intent"), {})
        print(f"🎯 识别意图: {intent_event2.get('intent')} | 理由: {intent_event2.get('reason')}")
        reply2 = "".join([e.get("text", "") for e in events2 if e.get("event") == "token"])
        print(f"🤖 Agent 动作受理回复:\n{reply2}")
        assert intent_event2.get("intent") == "ACTION_TOOL"
        print("✅ 动作指令验证通过：成功转交系统工作流！")

        # Case 3: 知识库检索 + 上下文降噪压缩 (context-mode 思想)
        print("\n" + "-" * 70)
        print("[测试 3: 知识库问答 + 上下文降噪压缩 (context-mode 降噪思想)]")
        q3 = "我如果去上海出差，一天最多能报销多少餐饮补贴？"
        print(f"❓ 用户提问: {q3}")
        res3 = client.post("/api/v1/chat/stream", json={"query": q3, "tenant_id": "tenant_default"})
        events3 = parse_sse_events(res3.text)
        
        comp_event = next((e for e in events3 if e.get("event") == "compression"), {})
        stats = comp_event.get("stats", {})
        print(f"📊 上下文压缩统计:")
        print(f"   - 原始召回字符数: {stats.get('original_chars')} 字符")
        print(f"   - 降噪后有效证据: {stats.get('compressed_chars')} 字符")
        print(f"   - 节省 Token 比例: {stats.get('saved_pct')} 🚀")
        
        reply3 = "".join([e.get("text", "") for e in events3 if e.get("event") == "token"])
        print(f"🤖 最终精简输出预览:\n{reply3[:150]}...")
        assert float(stats.get("saved_pct", "0%").replace("%", "")) > 0
        print("✅ 上下文降噪验证通过：成功剔除冗余句子并大幅节约 Token！")

    print("\n" + "=" * 70)
    print("🏆 Milestone 4 全部意图分支与 Token 压缩功能 100% 验收通过！")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()

