from __future__ import annotations

from fastapi import APIRouter, Request

from app.rate_limiter import rate_limiter
from app.schemas.auth import LoginRequest, LoginResponse, RefreshTokenRequest, UserInfo
from app.schemas.common import Result
from app.services.auth_service import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=Result[LoginResponse])
async def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not await rate_limiter.is_allowed(f"ratelimit:login:{client_ip}"):
        return Result.error("请求过于频繁，请稍后再试", code=429)

    result = await auth_service.login(req.username, req.password)
    if result is None:
        return Result.error("用户名或密码错误", code=401)
    return Result.success(LoginResponse(**result))


@router.post("/logout", response_model=Result[None])
async def logout(req: RefreshTokenRequest | None = None):
    refresh_token = req.refreshToken if req else None
    await auth_service.logout(refresh_token)
    return Result.success()


@router.post("/refresh", response_model=Result[LoginResponse])
async def refresh(req: RefreshTokenRequest):
    if not req.refreshToken:
        return Result.unauthorized("刷新令牌无效")
    result = await auth_service.refresh(req.refreshToken)
    if result is None:
        return Result.unauthorized("刷新令牌无效或已过期")
    return Result.success(LoginResponse(**result))


@router.get("/current", response_model=Result[UserInfo])
async def current_user(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.query_params.get("token", "")

    if not token:
        return Result.unauthorized()

    username = auth_service.get_username_by_token(token)
    if not username:
        return Result.unauthorized()

    return Result.success(UserInfo(username=username))
