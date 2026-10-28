from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class PostSchedule(Base):
    __tablename__ = "post_schedules"
    __table_args__ = (UniqueConstraint("post_id", "platform", "scheduled_at", name="uq_post_platform_schedule_time"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("content_posts.id", ondelete="CASCADE"), index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    post: Mapped["ContentPost"] = relationship()
