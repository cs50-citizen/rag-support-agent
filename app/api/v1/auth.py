from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user_repo import UserRepository
from app.core.security import create_access_token
from app.api.deps import get_current_user
from app.models.schema import User

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

class UserRegisterRequest(BaseModel):
    username: str = Field(..., example="alice_admin", description="用户名")
    email: str = Field(..., example="alice@enterprise.com", description="工作邮箱")
    password: str = Field(..., min_length=6, example="Admin123!", description="密码")
    role: str = Field("staff", example="admin", description="角色: admin / staff")
    tenant_id: str = Field("tenant_default", example="corp_finance", description="归属租户空间")

class UserLoginRequest(BaseModel):
    username: str = Field(..., example="alice_admin")
    password: str = Field(..., example="Admin123!")

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    tenant_id: str
    is_active: bool

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=UserResponse, summary="用户注册 (绑定租户与角色)")
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    ## 企业用户注册接口
    - 创建新用户
    - 绑定到对应的租户空间 (`tenant_id`)
    - 分配 RBAC 权限角色 (`admin` / `staff`)
    """
    repo = UserRepository(db)

    # 检查用户名和邮箱唯一性
    existing_user = await repo.get_by_username(req.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被占用")

    existing_email = await repo.get_by_email(req.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

    user = await repo.create_user(
        username=req.username,
        email=req.email,
        plain_password=req.password,
        role=req.role,
        tenant_id=req.tenant_id
    )
    return user


@router.post("/login", response_model=TokenResponse, summary="用户登录 (签发 JWT Token)")
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    ## 用户登录鉴权接口
    - 验证用户名与 bcrypt 加盐哈希密码
    - 签发包含 `sub`, `role`, `tenant_id` 的标准 JWT Access Token
    """
    repo = UserRepository(db)
    user = await repo.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 构造 JWT Payload
    token_payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id
    }
    token = create_access_token(data=token_payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/me", response_model=UserResponse, summary="获取当前登录用户画像 (依赖 JWT 验证)")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    ## 个人信息查询端点
    受 JWT 保护，提取 Token 中绑定的角色与所属企业租户
    """
    return current_user

