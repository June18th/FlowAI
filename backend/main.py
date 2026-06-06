from __future__ import annotations

import asyncio
import time
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.circuit_breakers import router as circuit_breakers_router
from app.api.executions import router as executions_router
from app.api.health import router as health_router
from app.api.benchmarks import router as benchmarks_router
from app.api.knowledge import router as knowledge_router
from app.api.llm_config import router as llm_config_router
from app.api.mcp_tools import router as mcp_tools_router
from app.api.node_types import router as node_types_router
from app.api.skills import router as skills_router
from app.api.workflows import router as workflows_router
from app.api.workflow_versions import router as workflow_versions_router
from app.config import settings
from app.database import engine
from app.engine.engine_selector import dag_engine
from app.engine.recovery_worker import run_recovery_worker
from app.logging_config import logger, setup_logging
from app.metrics import setup_instrumentator
from app.middleware.correlation import CorrelationIDMiddleware, get_request_id
from app.schemas.common import Result
from app.services.auth_service import auth_service
from app.telemetry import setup_telemetry


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=elapsed_ms,
            client=request.client.host if request.client else "",
            request_id=get_request_id(),
        )
        return response


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app.startup")

    # Startup validation: ping MySQL + Redis
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("startup.mysql.ok")
    except Exception as e:
        logger.error("startup.mysql.fail", error=str(e))
        raise RuntimeError(f"MySQL 连接失败: {e}") from e

    try:
        r = await auth_service._get_redis()
        await r.ping()
        logger.info("startup.redis.ok")
    except Exception as e:
        logger.error("startup.redis.fail", error=str(e))
        raise RuntimeError(f"Redis 连接失败: {e}") from e

    # Start recovery worker for orphaned executions
    recovery_stop = asyncio.Event()
    recovery_task = asyncio.create_task(
        run_recovery_worker(
            recovery_stop,
            auto_resume=settings.durable_auto_resume,
            dag_engine=dag_engine,
            orphan_threshold_s=settings.durable_orphan_threshold_seconds,
            scan_interval_s=settings.durable_scan_interval_seconds,
        )
    )

    try:
        yield
    finally:
        recovery_stop.set()
        await recovery_task
        await auth_service.close()
        logger.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="FlowAI API",
        description="AI workflow orchestration platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── Middleware stack (order matters) ──

    # 1. Correlation ID — must be first so downstream sees it
    app.add_middleware(CorrelationIDMiddleware)

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Request logging (uses request_id from step 1)
    app.add_middleware(LoggingMiddleware)

    # 4. API version backward compat
    class APIVersionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            path = request.url.path
            if path.startswith("/api/") and not path.startswith("/api/v1/"):
                new_path = path.replace("/api/", "/api/v1/", 1)
                request.scope["path"] = new_path
                request.scope["raw_path"] = new_path.encode()
            return await call_next(request)

    app.add_middleware(APIVersionMiddleware)

    # ── Observability ──

    # OpenTelemetry distributed tracing
    setup_telemetry(app)

    # Prometheus metrics endpoint + HTTP instrumentation
    setup_instrumentator(app)

    # ── Routes ──

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(workflows_router)
    app.include_router(workflow_versions_router)
    app.include_router(executions_router)
    app.include_router(circuit_breakers_router)
    app.include_router(node_types_router)
    app.include_router(llm_config_router)
    app.include_router(mcp_tools_router)
    app.include_router(skills_router)
    app.include_router(knowledge_router)
    app.include_router(benchmarks_router)

    # ── Global exception handler ──

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            error=str(exc),
            request_id=get_request_id(),
        )
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": str(exc), "data": None},
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.server_port)
