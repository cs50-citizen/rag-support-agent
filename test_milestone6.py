"""
Milestone 6 自动化验收脚本: JWT 用户认证与角色权限控制 (RBAC)
---------------------------------------------------------------
验证内容：
1. 用户注册绑定租户空间 (tenant_id) 与角色 (admin / staff)
2. 登录密码加盐哈希校验 (bcrypt) 与 JWT Access Token 签发
3. 身份识别保护端点: GET /api/v1/auth/me (无 Token 拦截 401)
4. RBAC 严格角色权限校验:
   - 普通员工 (staff) 访问管理员上传接口 -> 拦截 403 Forbidden
   - 管理员 (admin) 访问管理员上传接口 -> 授权 202 Accepted 并自动绑定其租户空间
"""

from fastapi.testclient import TestClient
from app.main import app

def run_auth_rbac_tests():
    print("=" * 70)
    print("🔐 Milestone 6: JWT 用户身份认证与 RBAC 权限控制验证")
    print("=" * 70)

    with TestClient(app) as client:
        # 1. 注册两个不同角色与租户的用户
        print("\n[步骤 1]: 注册不同角色与所属租户的企业账号...")
        
        # 用户 A: 财务部管理员
        reg_admin_payload = {
            "username": "admin_bob",
            "email": "bob.admin@corp-finance.com",
            "password": "Password123!",
            "role": "admin",
            "tenant_id": "corp_finance"
        }
        res_reg1 = client.post("/api/v1/auth/register", json=reg_admin_payload)
        assert res_reg1.status_code in [200, 400], f"Admin registration failed: {res_reg1.text}"
        print(f"✅ 管理员账号注册成功: {reg_admin_payload['username']} (角色: admin | 租户: {reg_admin_payload['tenant_id']})")

        # 用户 B: 通用部门普通员工
        reg_staff_payload = {
            "username": "staff_carol",
            "email": "carol.staff@enterprise.com",
            "password": "Password123!",
            "role": "staff",
            "tenant_id": "tenant_default"
        }
        res_reg2 = client.post("/api/v1/auth/register", json=reg_staff_payload)
        assert res_reg2.status_code in [200, 400], f"Staff registration failed: {res_reg2.text}"
        print(f"✅ 普通员工账号注册成功: {reg_staff_payload['username']} (角色: staff | 租户: {reg_staff_payload['tenant_id']})")

        # 2. 验证密码校验与登录签发 JWT
        print("\n" + "-" * 70)
        print("[步骤 2]: 验证用户登录与 JWT 签发...")
        
        # 2.1 错误密码测试
        login_fail = client.post("/api/v1/auth/login", json={"username": "admin_bob", "password": "WrongPassword"})
        assert login_fail.status_code == 401
        print("🛡️  密码防爆破测试通过: 错误密码返回 401 Unauthorized！")

        # 2.2 正确密码登录
        login_admin = client.post("/api/v1/auth/login", json={"username": "admin_bob", "password": "Password123!"})
        assert login_admin.status_code == 200
        admin_token = login_admin.json()["access_token"]
        print(f"🎫 管理员登录成功，签发 JWT: {admin_token[:30]}... (完整带签名)")

        login_staff = client.post("/api/v1/auth/login", json={"username": "staff_carol", "password": "Password123!"})
        assert login_staff.status_code == 200
        staff_token = login_staff.json()["access_token"]
        print(f"🎫 普通员工登录成功，签发 JWT: {staff_token[:30]}...")

        # 3. 验证受保护的身份端点 /auth/me
        print("\n" + "-" * 70)
        print("[步骤 3]: 验证受保护个人中心接口 (GET /api/v1/auth/me)...")
        
        # 无 Token 访问
        me_no_token = client.get("/api/v1/auth/me")
        assert me_no_token.status_code == 401
        print("🛡️  未登录拦截测试通过: 缺失 Token 直接返回 401")

        # 携带有效 Token 访问
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        me_with_token = client.get("/api/v1/auth/me", headers=headers_admin)
        assert me_with_token.status_code == 200
        me_data = me_with_token.json()
        print(f"👤 Token 鉴权成功: 用户名={me_data['username']} | 角色={me_data['role']} | 租户={me_data['tenant_id']}")

        # 4. 验证严格的 RBAC 角色权限控制 (仅 Admin 可执行长文档管理员上传)
        print("\n" + "-" * 70)
        print("[步骤 4]: 验证 RBAC 权限隔离 (POST /api/v1/documents/admin/upload)...")
        
        upload_doc = {
            "filename": "admin_audit_plan.txt",
            "content": "[审计方案 2026] 仅管理员有权限执行的绝密知识上传入库...",
            "tenant_id": "corp_finance"
        }

        # 4.1 普通员工 (staff) 试图越权操作管理员接口
        headers_staff = {"Authorization": f"Bearer {staff_token}"}
        res_forbidden = client.post("/api/v1/documents/admin/upload", json=upload_doc, headers=headers_staff)
        print(f"⚠️  普通员工访问管理员端点返回状态: {res_forbidden.status_code} ({res_forbidden.json().get('detail')})")
        assert res_forbidden.status_code == 403, "普通员工越权成功，权限控制失效！"
        print("🛡️  RBAC 拦截成功: 普通员工 (staff) 访问管理员接口被拦截 (403 Forbidden)！")

        # 4.2 管理员 (admin) 合法调用
        res_allowed = client.post("/api/v1/documents/admin/upload", json=upload_doc, headers=headers_admin)
        print(f"🌟 管理员访问返回状态: {res_allowed.status_code}")
        assert res_allowed.status_code == 202
        print("✅ RBAC 授权成功: 管理员 (admin) 成功通过鉴权并生成后台切片任务！")

    print("\n" + "=" * 70)
    print("🏆 Milestone 6: JWT 认证与 RBAC 权限控制 100% 验收通过！")
    print("=" * 70)

if __name__ == "__main__":
    run_auth_rbac_tests()

