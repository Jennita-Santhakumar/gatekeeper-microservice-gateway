from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    content: str
    created_at: datetime


class PostList(BaseModel):
    items: list[PostOut]
    limit: int
    offset: int
    total: int


class HealthStatus(BaseModel):
    status: str
    database: str
