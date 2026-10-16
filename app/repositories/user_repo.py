from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schema import User, Tenant
from app.core.security import hash_password, verify_password

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        username: str,
        email: str,
        plain_password: str,
        role: str = "staff",
        tenant_id: str = "tenant_default"
    ) -> User:
        # 确保对应租户存在
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        res = await self.db.execute(tenant_stmt)
        tenant = res.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(id=tenant_id, name=f"{tenant_id} 空间")
            self.db.add(tenant)
            await self.db.flush()

        hashed = hash_password(plain_password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
            role=role,
            tenant_id=tenant_id,
            is_active=True
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, username: str, plain_password: str) -> Optional[User]:
        user = await self.get_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(plain_password, user.hashed_password):
            return None
        return user

