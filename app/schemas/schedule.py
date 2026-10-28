from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["instagram", "facebook", "linkedin"]

class ScheduleCreate(BaseModel):
    post_id: int
    platforms: list[Platform] = Field(min_length=1, max_length=3)
    scheduled_at: datetime
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)

class ScheduleOut(BaseModel):
    id: int
    post_id: int
    owner_id: int
    platform: str
    scheduled_at: datetime
    timezone: str
    status: str
    note: str
    created_at: datetime
    topic: str | None = None
    business_name: str | None = None
    caption_preview: str | None = None
    model_config = ConfigDict(from_attributes=True)
