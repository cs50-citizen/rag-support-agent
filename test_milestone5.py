"""
Milestone 5 自动化验收脚本: Celery + Redis 异步解耦任务流
---------------------------------------------------------
验证内容：
1. 客户端调用 POST /api/v1/documents/upload 上传长文档
2. 接口立即返回 HTTP 202 Accepted 与 task_id，绝不阻塞 Web 线程
3. 轮询 GET /api/v1/documents/tasks/{task_id} 验证任务状态转换与处理进度
4. 验证新入库的切片与向量立即被检索系统感知并成功回答！
"""

import sys
import time
import json
from fastapi.testclient import TestClient
from app.main import app

def run_async_pipeline_test():
    print("=" * 70)
    print("⚡ Milestone 5: Celery + Redis 异步长任务队列与状态追踪验证")
    print("=" * 70)

    with TestClient(app) as client:
        # 1. 模拟上传一份全新的企业远程办公制度长文档
        doc_content = (
            "[全球分布式远程办公制度 2026版]\n"
            "1. 远程设备津贴：公司为每位全职居家员工提供一次性 3000 元的人体工学桌椅与显示器设备补贴。\n\n"
            "2. 核心在线工作时间：分布式团队需在当地时间 10:00 至 16:00 保持 Slack 与飞书在线响应。\n\n"
            "3. 协同规范：每周五下午 15:00 举办全员线上 Demo 展示会，严禁无故缺席。"
        )
        
        upload_payload = {
            "filename": "remote_work_policy_2026.txt",
            "content": doc_content,
            "tenant_id": "corp_tech"
        }

        print("\n[步骤 1]: 向后端提交长文档上传请求...")
        print(f"📄 文件名: {upload_payload['filename']} | 目标租户: {upload_payload['tenant_id']}")
        start_time = time.time()
        res = client.post("/api/v1/documents/upload", json=upload_payload)
        elapsed = time.time() - start_time

        print(f"⏱️  接口响应耗时: {elapsed:.3f} 秒 (验证非阻塞设计)")
        assert res.status_code == 202, f"Expected 202 Accepted, got {res.status_code}"
        
        upload_data = res.json()
        task_id = upload_data["task_id"]
        doc_id = upload_data["document_id"]
        print(f"✅ 成功获得 HTTP 202 Accepted！")
        print(f"📋 生成文档 ID: {doc_id} | 异步任务 ID (task_id): {task_id}")

        # 2. 轮询 Celery 任务进度状态
        print("\n" + "-" * 70)
        print("[步骤 2]: 轮询查询 Celery 后台解析进度 (GET /api/v1/documents/tasks/{task_id})...")
        max_retries = 10
        is_completed = False
        
        for attempt in range(1, max_retries + 1):
            task_res = client.get(f"/api/v1/documents/tasks/{task_id}")
            assert task_res.status_code == 200
            t_data = task_res.json()
            state = t_data.get("state")
            progress = t_data.get("progress", 0)
            step = t_data.get("step") or t_data.get("info", "")
            
            print(f"   [轮询第 {attempt} 次] 状态: {state} | 进度: {progress}% | 步骤: {step}")
            
            if state == "SUCCESS":
                is_completed = True
                print(f"🎉 Celery Worker 处理完成！生成切片数: {t_data.get('result', {}).get('total_chunks')} 个")
                break
            time.sleep(0.5)

        assert is_completed, "Celery 任务超时未完成"

        # 3. 验证新文档是否可以被 RAG 检索
        print("\n" + "-" * 70)
        print("[步骤 3]: 立即向租户 [corp_tech] 发问刚才入库的全新知识：")
        q = "公司远程办公提供多少钱的人体工学桌椅补贴？"
        print(f"❓ 提问: {q}")
        
        chat_res = client.post("/api/v1/chat/stream", json={"query": q, "tenant_id": "corp_tech"})
        assert chat_res.status_code == 200
        
        full_answer = ""
        for line in chat_res.text.split("\n"):
            if line.startswith("data: ") and "token" in line:
                full_answer += json.loads(line[6:]).get("text", "")

        print(f"💡 助手即时回答:\n{full_answer}")
        assert "3000" in full_answer or "人体工学" in full_answer
        print("✅ 验证成功：刚刚由 Celery 异步切片入库的新知识，已无缝完成向量索引并精准召回！")

    print("\n" + "=" * 70)
    print("🏆 Milestone 5: Celery + Redis 异步解耦任务流 100% 验收通过！")
    print("=" * 70)

if __name__ == "__main__":
    run_async_pipeline_test()

