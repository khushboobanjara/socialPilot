from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_audience: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="English", nullable=False)
    brand_voice: Mapped[str] = mapped_column(String(100), default="Friendly and professional", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner: Mapped["User"] = relationship(back_populates="businesses")
    content_posts: Mapped[list["ContentPost"]] = relationship(back_populates="business", cascade="all, delete-orphan")
