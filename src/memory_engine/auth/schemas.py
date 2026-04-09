from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str


class SessionUser(BaseModel):
    email: str
    display_name: str
    role: str


class SessionResponse(BaseModel):
    token: str
    user: SessionUser
