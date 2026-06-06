from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine
from app.schemas.common import Result
from app.services.auth_service import auth_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=Result[dict])
async def health_check():
    mysql_ok = False
    redis_ok = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        mysql_ok = True
    except Exception:
        pass

    try:
        r = await auth_service._get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    status = "ok" if mysql_ok and redis_ok else "degraded"
    return Result.success({
        "status": status,
        "mysql": "ok" if mysql_ok else "disconnected",
        "redis": "ok" if redis_ok else "disconnected",
    })


@router.get("/live", response_model=Result[dict])
async def liveness():
    """Kubernetes liveness probe — is the process alive?"""
    return Result.success({"status": "alive"})


@router.get("/ready", response_model=Result[dict])
async def readiness():
    """Kubernetes readiness probe — can the process serve traffic?"""
    mysql_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        mysql_ok = True
    except Exception:
        pass

    redis_ok = False
    try:
        r = await auth_service._get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    ready = mysql_ok and redis_ok
    return Result.success({
        "status": "ready" if ready else "not_ready",
        "mysql": "ok" if mysql_ok else "disconnected",
        "redis": "ok" if redis_ok else "disconnected",
    })
