from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
Platform = Literal['instagram','facebook','linkedin']
ContentType = Literal['promotional','educational','behind_the_scenes','announcement','testimonial','engagement']
class GenerateRequest(BaseModel):
    business_id: int
    topic: str = Field(min_length=3,max_length=255)
    goal: str = Field(default='Engagement',max_length=120)
    content_type: ContentType = 'educational'
    platforms: list[Platform] = Field(default_factory=lambda:['instagram','facebook','linkedin'],min_length=1,max_length=3)
    offer_details: str = Field(default='',max_length=1500)
    include_emojis: bool = True
class VariantEdit(BaseModel):
    platform: Platform
    caption: str = Field(min_length=1,max_length=10000)
    hashtags: list[str] = Field(default_factory=list,max_length=30)
    call_to_action: str = Field(default='',max_length=500)
class ContentEdit(BaseModel):
    variants: list[VariantEdit] | None = None
class VariantOut(BaseModel):
    id:int; platform:str; caption:str; hashtags:list[str]; call_to_action:str
    model_config=ConfigDict(from_attributes=True)
class ContentOut(BaseModel):
    id:int; business_id:int; topic:str; goal:str; content_type:str; offer_details:str; status:str; created_at:datetime; updated_at:datetime; variants:list[VariantOut]
    model_config=ConfigDict(from_attributes=True)
