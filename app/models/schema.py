import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base

VECTOR_DIM = 768  # 适配 Gemini text-embedding-004 的 768 维向量

class Tenant(Base):
    """
    租户表 (Multi-Tenant Core)
    不同企业客户、或同一企业下的不同事业群对应独立的租户 ID。
    """
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 如: "corp_hr", "corp_finance"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关联文档与用户
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class Document(Base):
    """
    文档主表
    记录上传的原始文件信息与异步解析状态
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), default="txt")
    status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING, PROCESSING, COMPLETED, FAILED
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关联
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_doc_tenant_status", "tenant_id", "status"),
    )


class DocumentChunk(Base):
    """
    文档切片与向量存储表 (Vector Storage with Multi-Tenant Isolation)
    每个知识切片都携带 tenant_id，实现数据库级别的物理/逻辑隔离。
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 结构化元数据 (借鉴 xerj 设计思想：包含段落锚点、页码、提取标签等)
    meta_info: Mapped[dict] = mapped_column(JSON, default=dict)

    # 768 维语义向量字段 (pgvector 核心)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(VECTOR_DIM), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关联
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        # 核心多租户组合索引：查询时必定先根据 tenant_id 命中分区或索引范围
        Index("idx_chunk_tenant_doc", "tenant_id", "document_id"),
    )


class User(Base):
    """
    用户表 (RBAC 角色权限与多租户归属绑定)
    支持角色: admin (租户管理员，具备文档上传与管理权), staff (普通员工，具备智能问答权)
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="staff")  # "admin", "staff"
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


