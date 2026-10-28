from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=5000)
    target_audience: str = Field(default="", max_length=255)
    language: str = Field(default="English", max_length=50)
    brand_voice: str = Field(default="Friendly and professional", max_length=100)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)

class BusinessUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    target_audience: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, max_length=50)
    brand_voice: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=80)

class BusinessResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    category: str
    description: str
    target_audience: str
    language: str
    brand_voice: str
    timezone: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
