from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("owner_id", "platform", name="uq_social_account_owner_platform"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    remote_account_id: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    account_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Connected account")
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="connected")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

class OAuthState(Base):
    __tablename__ = "social_oauth_states"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    state: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
