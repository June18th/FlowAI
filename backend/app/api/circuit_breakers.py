from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_auth
from app.engine.circuit_breaker import _breakers, get_breaker
from app.schemas.common import Result

router = APIRouter(prefix="/api/v1/executions/circuit-breakers", tags=["circuit-breakers"])


@router.get("", response_model=Result[list[dict]])
async def list_circuit_breakers(_: str = Depends(require_auth)):
    items = []
    for name, breaker in _breakers.items():
        items.append({
            "nodeType": name,
            "state": breaker._state.value,
            "failures": breaker._failures,
            "failureThreshold": breaker.failure_threshold,
            "halfOpenAttempts": breaker._half_open_attempts,
            "halfOpenMax": breaker.half_open_max,
        })
    return Result.success(items)


@router.post("/{node_type}/reset", response_model=Result[dict])
async def reset_circuit_breaker(node_type: str, _: str = Depends(require_auth)):
    breaker = get_breaker(node_type)
    breaker.success()
    return Result.success({
        "nodeType": node_type,
        "state": breaker._state.value,
        "message": "熔断器已重置为关闭状态",
    })
