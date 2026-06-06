from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session as _async_session_factory
from app.schemas.common import Result
from app.services.auth_service import auth_service

security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> str:
    """Extract and validate JWT, return username."""
    token = None

    # Try Authorization header first
    if credentials:
        token = credentials.credentials
    # Also try query param (for SSE)
    if not token:
        token = request.query_params.get("token")

    if not token:
        return ""

    username = auth_service.validate_token(token)
    return username or ""


async def require_auth(username: str = Depends(get_current_user)) -> str:
    """Require valid authentication, raise 401 via dependency override."""
    if not username:
        raise HTTPException(status_code=401, detail="未认证或认证已过期")
    return username
