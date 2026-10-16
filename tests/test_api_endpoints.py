import pytest
import json

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

def test_auth_workflow(client):
    # 注册
    reg_data = {
        "username": "pytest_user",
        "email": "pytest@enterprise.com",
        "password": "Password123!",
        "role": "staff",
        "tenant_id": "tenant_default"
    }
    client.post("/api/v1/auth/register", json=reg_data)

    # 登录
    login_res = client.post("/api/v1/auth/login", json={
        "username": "pytest_user",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert len(token) > 20

    # 身份认证
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "pytest_user"

def test_chat_stream_sse(client):
    req_body = {
        "query": "你好",
        "tenant_id": "tenant_default"
    }
    res = client.post("/api/v1/chat/stream", json=req_body)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    assert "data: " in res.text

def test_async_document_upload_and_status(client):
    payload = {
        "filename": "pytest_doc.txt",
        "content": "[pytest 测试规章]\n全员需严格编写自动化单元测试并维持 80% 覆盖率。",
        "tenant_id": "tenant_default"
    }
    upload_res = client.post("/api/v1/documents/upload", json=payload)
    assert upload_res.status_code == 202
    data = upload_res.json()
    task_id = data["task_id"]

    # 查询任务状态
    task_res = client.get(f"/api/v1/documents/tasks/{task_id}")
    assert task_res.status_code == 200
    assert task_res.json()["state"] in ["PROCESSING", "SUCCESS"]

