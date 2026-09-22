"""Pydantic request/response schemas for users-service."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    username: str
    created_at: datetime.datetime


class UserList(BaseModel):
    items: list[UserOut]
    limit: int
    offset: int
    total: int


class HealthStatus(BaseModel):
    status: str
    database: str
