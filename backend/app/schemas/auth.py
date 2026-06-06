from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserInfo(BaseModel):
    username: str


class LoginResponse(BaseModel):
    token: str
    refreshToken: str
    user: UserInfo


class RefreshTokenRequest(BaseModel):
    refreshToken: str | None = None
