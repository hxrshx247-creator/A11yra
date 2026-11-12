from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.product.db import Base, new_id, now


class Id:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class Created:
    created_at: Mapped[datetime] = mapped_column(default=now)


class User(Id, Created, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(default=False)


class Workspace(Id, Created, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(100))
    personal_owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)


class Membership(Created, Base):
    __tablename__ = "memberships"
    __table_args__ = (CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="valid_role"),)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10))


class Session(Id, Created, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    access_until: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)


class AccountToken(Created, Base):
    __tablename__ = "account_tokens"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Invite(Id, Created, Base):
    __tablename__ = "invitations"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(10))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Document(Id, Created, Base):
    __tablename__ = "documents"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="active")
    expires_at: Mapped[datetime] = mapped_column(index=True)
    history_until: Mapped[datetime] = mapped_column(index=True)
    warning_sent: Mapped[bool] = mapped_column(default=False)


class DocumentChild:
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)


class AuditRecord(Id, Created, DocumentChild, Base):
    __tablename__ = "audits"
    summary: Mapped[dict] = mapped_column(JSON)
    findings: Mapped[list] = mapped_column(JSON)


class FixRecord(Id, Created, DocumentChild, Base):
    __tablename__ = "fixes"
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    result: Mapped[dict] = mapped_column(JSON)


class ExportRecord(Id, Created, DocumentChild, Base):
    __tablename__ = "exports"
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    format: Mapped[str] = mapped_column(String(16))


class AuditLog(Id, Created, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("activity_workspace_date", "workspace_id", "created_at"),)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"))
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(40))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str | None] = mapped_column(String(36))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent_short: Mapped[str | None] = mapped_column(String(120))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UsageEvent(Id, Created, Base):
    __tablename__ = "usage_events"
    __table_args__ = (Index("usage_workspace_kind_date", "workspace_id", "kind", "created_at"),)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))


class Subscription(Created, Base):
    __tablename__ = "subscriptions"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    plan: Mapped[str] = mapped_column(String(16), default="free")
    stripe_subscription: Mapped[str | None] = mapped_column(String(100), unique=True)
    stripe_event_at: Mapped[int] = mapped_column(default=0)


class ReaderShare(Id, Created, DocumentChild, Base):
    __tablename__ = "reader_shares"
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)


class ApiKey(Id, Created, Base):
    __tablename__ = "api_keys"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
