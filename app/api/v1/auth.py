from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.user_repo import UserRepository
from app.core.security import create_access_token
from app.api.deps import get_current_user
from app.models.schema import User

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])

class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        json_schema_extra={"example": "alice_admin"},
        description="Unique username"
    )
    email: str = Field(
        ...,
        json_schema_extra={"example": "alice@enterprise.com"},
        description="Corporate email address"
    )
    password: str = Field(
        ...,
        min_length=6,
        json_schema_extra={"example": "Admin123!"},
        description="User password"
    )
    role: str = Field(
        "staff",
        json_schema_extra={"example": "admin"},
        description="RBAC Role: 'admin' or 'staff'"
    )
    tenant_id: str = Field(
        "tenant_default",
        json_schema_extra={"example": "tenant_default"},
        description="Tenant space binding"
    )

class UserLoginRequest(BaseModel):
    username: str = Field(..., json_schema_extra={"example": "alice_admin"})
    password: str = Field(..., json_schema_extra={"example": "Admin123!"})

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    tenant_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

@router.post("/register", response_model=UserResponse, summary="User Registration (Tenant & Role Binding)")
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    ## Enterprise User Registration Endpoint
    - Registers a new user account
    - Binds user to target tenant isolation scope (`tenant_id`)
    - Assigns RBAC security role (`admin` / `staff`)
    """
    repo = UserRepository(db)

    # Check username and email uniqueness
    existing_user = await repo.get_by_username(req.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    existing_email = await repo.get_by_email(req.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = await repo.create_user(
        username=req.username,
        email=req.email,
        plain_password=req.password,
        role=req.role,
        tenant_id=req.tenant_id
    )
    return user

@router.post("/login", response_model=TokenResponse, summary="User Login (JWT Token Issuance)")
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    ## User Authentication & JWT Issuance Endpoint
    - Verifies username against bcrypt-salted password hash
    - Issues signed JWT access token containing `sub`, `role`, and `tenant_id`
    """
    repo = UserRepository(db)
    user = await repo.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

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

@router.get("/me", response_model=UserResponse, summary="Get Current User Profile (JWT Protected)")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    ## Current User Identity Endpoint
    Protected by JWT authentication; extracts role and tenant scope from verified token claims.
    """
    return current_user
