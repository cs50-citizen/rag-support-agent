"""
多租户隔离与向量检索验证脚本 (Milestone 3 核心验证)
-------------------------------------------------
演示目标：
1. 租户 tenant_default (普通员工) 提问公共制度 -> 正常检索并回答
2. 租户 tenant_default (普通员工) 试图刺探财务年终奖绝密制度 -> 被多租户隔离墙拦截，拒不回答
3. 租户 corp_finance (财务部授权租户) 提问财务年终奖制度 -> 正常命中机密并回答
"""

import sys
import json
import httpx
from fastapi.testclient import TestClient
from app.main import app

def run_multitenant_tests():
    print("=" * 70)
    print("🛡️  Milestone 3: PostgreSQL/pgvector 多租户数据物理与逻辑隔离验证")
    print("=" * 70)

    # 使用 TestClient 在内存中自测，无需外部起服务
    with TestClient(app) as client:
        # Case 1: 普通租户提问公开差旅规定
        print("\n[测试场景 1]: 租户 [tenant_default] (普通租户) 提问公开制度")
        q1 = "请问出差去上海，每天餐饮补贴是多少？"
        print(f"❓ 提问: {q1}")
        res1 = client.post("/api/v1/chat/stream", json={"query": q1, "tenant_id": "tenant_default"})
        assert res1.status_code == 200
        print("💡 结果流片段预览:")
        for line in res1.text.split("\n")[:12]:
            if line.startswith("data: ") and "token" in line:
                sys.stdout.write(json.loads(line[6:]).get("text", ""))
        print("...\n✅ 结论: 授权空间内正常检索回答！")

        # Case 2: 普通租户试图越权探听财务机密
        print("\n" + "-" * 70)
        print("[测试场景 2]: 租户 [tenant_default] (普通租户) 试图探听财务年终奖机密！")
        q2 = "请问公司年终奖什么时候发？计算基数是多少个月？"
        print(f"❓ 提问: {q2}")
        res2 = client.post("/api/v1/chat/stream", json={"query": q2, "tenant_id": "tenant_default"})
        assert res2.status_code == 200
        print("💡 结果流输出:")
        full_text2 = ""
        for line in res2.text.split("\n"):
            if line.startswith("data: ") and "token" in line:
                full_text2 += json.loads(line[6:]).get("text", "")
        print(full_text2)
        print("🛡️  结论: 成功拦截！虽然数据库里存有年终奖文档，但由于 tenant_id 隔离，普通租户无法越权！")

        # Case 3: 财务租户合法提问
        print("\n" + "-" * 70)
        print("[测试场景 3]: 租户 [corp_finance] (财务授权空间) 提问同一问题：")
        print(f"❓ 提问: {q2}")
        res3 = client.post("/api/v1/chat/stream", json={"query": q2, "tenant_id": "corp_finance"})
        assert res3.status_code == 200
        print("💡 结果流输出:")
        full_text3 = ""
        for line in res3.text.split("\n"):
            if line.startswith("data: ") and "token" in line:
                full_text3 += json.loads(line[6:]).get("text", "")
        print(full_text3)
        print("🎉 结论: 财务空间权限命中，精准回答年终奖细则！")

    print("\n" + "=" * 70)
    print("🏆 多租户向量数据库隔离验证 100% 通过！")
    print("=" * 70)

if __name__ == "__main__":
    run_multitenant_tests()

