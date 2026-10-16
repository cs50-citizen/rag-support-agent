from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import decode_access_token
from app.repositories.user_repo import UserRepository
from app.models.schema import User

security_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    依赖项：强制解析并验证 JWT Token，返回已认证的用户对象
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少身份凭证，请携带 Bearer JWT Token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 格式异常")

    repo = UserRepository(db)
    user = await repo.get_by_id(int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")

    return user

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    可选认证依赖：若携带合法的 Token 则返回 User，否则返回 None (用于平滑兼容模式)
    """
    if not credentials or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    repo = UserRepository(db)
    return await repo.get_by_id(int(payload["sub"]))

def require_roles(allowed_roles: List[str]):
    """
    RBAC 权限检查依赖工厂函数：验证用户角色是否在授权范围内
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足：当前角色 [{current_user.role}] 无法访问此资源，需要 [{', '.join(allowed_roles)}] 权限"
            )
        return current_user
    return role_checker

# 便捷快捷依赖
require_admin = require_roles(["admin"])
require_staff = require_roles(["admin", "staff"])

