"""
客户端流式测试脚本 (模拟前端消费 SSE 流)
---------------------------------------
运行前请确保 FastAPI 服务已启动：
uvicorn app.main:app --port 8000
"""

import sys
import json
import httpx

API_URL = "http://127.0.0.1:8000/api/v1/chat/stream"

def test_streaming():
    payload = {
        "query": "请问出差去上海，每天餐饮补贴是多少？",
        "tenant_id": "corp_sales"
    }

    print("=" * 60)
    print(f"📡 正在向 FastAPI 后端发起 SSE 流式请求: {API_URL}")
    print(f"❓ 用户提问: {payload['query']}")
    print("=" * 60)

    try:
        with httpx.stream("POST", API_URL, json=payload, timeout=60.0) as response:
            if response.status_code != 200:
                print(f"❌ 请求失败，状态码: {response.status_code}")
                return

            print("🤖 助手实时流式输出 (打字机效果):")
            print("-" * 40)
            
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                
                raw_json = line[len("data: "):]
                try:
                    data = json.loads(raw_json)
                    event_type = data.get("event")

                    if event_type == "retrieving":
                        print(f"🔍 [{data.get('message')}]")
                    elif event_type == "token":
                        # 逐字打印到控制台，不换行，flush 刷新缓冲区
                        sys.stdout.write(data.get("text", ""))
                        sys.stdout.flush()
                    elif event_type == "done":
                        print("\n" + "-" * 40)
                        print("📚 参考资料来源 (References):")
                        for ref in data.get("references", []):
                            print(f"   - 文件: {ref['source']} (切片: {ref['id']}, 相似度: {ref['score']})")
                except json.JSONDecodeError:
                    continue

        print("\n" + "=" * 60)
        print("🎉 SSE 流式问答测试成功完成！")
        print("=" * 60)

    except httpx.ConnectError:
        print("❌ 无法连接到后端服务器，请先启动服务：")
        print("   .\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000")

if __name__ == "__main__":
    test_streaming()

