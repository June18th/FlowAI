from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_db, require_auth
from app.engine.engine_selector import engine_selector
from app.models.execution import ExecutionRecord, ExecutionSnapshot, ExecutionVariable
from app.schemas.common import Result
from app.schemas.execution import (
    ExecutionRequest,
    ResumeExecutionRequest,
)
from app.engine.dag_engine import _set_cancel_flag
from app.services.execution_comparison_service import execution_comparison_service
from app.services.workflow_service import workflow_service

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


# ── POST /api/executions ──────────────────────────────────────────
@router.post("", response_model=Result[dict])
async def execute_workflow(
    req: ExecutionRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    wf = await workflow_service.get_workflow_entity(db, req.workflowId)
    if not wf:
        return Result.error("工作流不存在", code=404)

    engine = engine_selector.select(wf)
    try:
        result = await engine.execute(wf, req.inputData, db=db)
        return Result.success(result)
    except Exception as e:
        return Result.error(str(e))


# ── GET /api/executions/stream ─────────────────────────────────────
@router.get("/stream")
async def execute_workflow_stream(
    request: Request,
    workflowId: int = Query(...),
    inputData: str = Query(...),
    token: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    wf = await workflow_service.get_workflow_entity(db, workflowId)
    if not wf:
        async def error_gen():
            yield {"event": "ERROR", "data": json.dumps({"message": "工作流不存在"})}
        return EventSourceResponse(error_gen())

    engine = engine_selector.select(wf)
    event_queue: asyncio.Queue = asyncio.Queue()

    def event_callback(event: dict[str, Any]):
        asyncio.ensure_future(event_queue.put(event))

    async def event_generator():
        task = asyncio.create_task(_run_engine(engine, wf, inputData, event_callback, db))
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                event_type = event.pop("eventType", "message")
                yield {"event": event_type, "data": json.dumps(event, default=str)}
                if event_type in ("WORKFLOW_COMPLETE", "ERROR"):
                    break
            except asyncio.TimeoutError:
                if task.done():
                    if task.exception():
                        yield {"event": "ERROR", "data": json.dumps({"message": str(task.exception())})}
                    break
                continue
        await task

    return EventSourceResponse(event_generator())


async def _run_engine(engine, wf, input_data: str, callback, db):
    try:
        await engine.execute(wf, input_data, event_callback=callback, db=db)
    except Exception as e:
        callback({"eventType": "ERROR", "message": str(e)})


# ── GET /api/executions ────────────────────────────────────────────
@router.get("", response_model=Result[dict])
async def list_executions(
    workflowId: int | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    conditions = [ExecutionRecord.deleted == 0]
    if workflowId is not None:
        conditions.append(ExecutionRecord.flow_id == workflowId)
    if status:
        conditions.append(ExecutionRecord.status == status)

    count_stmt = select(ExecutionRecord).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

    stmt = (
        select(ExecutionRecord)
        .where(*conditions)
        .order_by(ExecutionRecord.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    return Result.success({
        "items": [_execution_to_dict(r) for r in records],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    })


# ── GET /api/executions/orphaned ───────────────────────────────────
@router.get("/orphaned", response_model=Result[dict])
async def list_orphaned_executions(
    thresholdSeconds: int = Query(60, ge=10),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    cutoff = datetime.utcnow() - timedelta(seconds=thresholdSeconds)
    stmt = select(ExecutionRecord).where(
        ExecutionRecord.status == "RUNNING",
        ExecutionRecord.heartbeat_at.isnot(None),
        ExecutionRecord.heartbeat_at < cutoff,
        ExecutionRecord.deleted == 0,
    ).order_by(ExecutionRecord.heartbeat_at)
    result = await db.execute(stmt)
    orphans = result.scalars().all()
    return Result.success({
        "items": [_execution_to_dict(o) for o in orphans],
        "total": len(orphans),
    })


# ── GET /api/executions/latest ─────────────────────────────────────
@router.get("/latest", response_model=Result[dict | None])
async def get_latest_execution(
    workflowId: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = (
        select(ExecutionRecord)
        .where(ExecutionRecord.flow_id == workflowId, ExecutionRecord.deleted == 0)
        .order_by(ExecutionRecord.id.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return Result.success(None)
    return Result.success(_execution_to_dict(record))


# ── GET /api/executions/{execution_id}/snapshots ───────────────────
@router.get("/{execution_id}/snapshots", response_model=Result[list[dict]])
async def get_execution_snapshots(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = (
        select(ExecutionSnapshot)
        .where(ExecutionSnapshot.execution_id == execution_id)
        .order_by(ExecutionSnapshot.execution_order)
    )
    result = await db.execute(stmt)
    return Result.success([_snapshot_to_dict(s) for s in result.scalars().all()])


# ── GET /api/executions/{execution_id}/compare ──────────────────────

@router.get("/{execution_id}/compare", response_model=Result[dict])
async def compare_executions(
    execution_id: int,
    other: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await execution_comparison_service.compare_executions(db, execution_id, other)
    if result is None:
        return Result.error("执行记录不存在", code=404)
    return Result.success(result)


# ── GET /api/executions/{execution_id}/variables ───────────────────
@router.get("/{execution_id}/variables", response_model=Result[list[dict]])
async def get_execution_variables(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(ExecutionVariable).where(ExecutionVariable.execution_id == execution_id)
    result = await db.execute(stmt)
    return Result.success([_variable_to_dict(v) for v in result.scalars().all()])


# ── POST /api/executions/{execution_id}/cancel ──────────────────────

@router.post("/{execution_id}/cancel", response_model=Result[dict])
async def cancel_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(ExecutionRecord).where(
        ExecutionRecord.id == execution_id,
        ExecutionRecord.deleted == 0,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return Result.error("执行记录不存在", code=404)
    if record.status != "RUNNING":
        return Result.error(f"只能取消运行中的执行，当前状态: {record.status}", code=400)

    await _set_cancel_flag(execution_id)
    return Result.success({
        "executionId": execution_id,
        "message": "取消请求已发送，当前节点完成后将停止并保存检查点",
    })


# ── POST /api/executions/{execution_id}/resume ─────────────────────
@router.post("/{execution_id}/resume", response_model=Result[dict])
async def resume_execution(
    execution_id: int,
    req: ResumeExecutionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    stmt = select(ExecutionRecord).where(
        ExecutionRecord.id == execution_id,
        ExecutionRecord.deleted == 0,
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        return Result.error("执行记录不存在", code=404)

    if record.status == "SUCCESS":
        return Result.success(_execution_to_dict(record))

    if not record.execution_state:
        return Result.error("该执行记录没有检查点，无法恢复", code=400)

    wf = await workflow_service.get_workflow_entity(db, record.flow_id)
    if not wf:
        return Result.error("工作流不存在", code=404)

    dag_engine = engine_selector._engines.get("dag")
    if not dag_engine:
        return Result.error("DAG 引擎不可用", code=500)

    try:
        exec_result = await dag_engine.execute(
            wf,
            str(record.input_data.get("input", "") if record.input_data else ""),
            db=db,
            resume_record=record,
        )
        return Result.success(exec_result)
    except Exception as e:
        return Result.error(str(e))


# ── serialization ──────────────────────────────────────────────────

def _execution_to_dict(r: ExecutionRecord) -> dict:
    return {
        "executionId": r.id,
        "flowId": r.flow_id,
        "status": r.status,
        "inputData": r.input_data,
        "outputData": r.output_data,
        "nodeResults": r.node_results or [],
        "duration": r.duration,
        "errorMessage": r.error_message,
        "engineType": r.engine_type,
        "lastCompletedNodeId": r.last_completed_node_id,
        "workerId": r.worker_id,
        "heartbeatAt": r.heartbeat_at.isoformat() if r.heartbeat_at else None,
        "executedAt": r.executed_at.isoformat() if r.executed_at else None,
    }


def _snapshot_to_dict(s: ExecutionSnapshot) -> dict:
    return {
        "id": s.id, "executionId": s.execution_id, "flowId": s.flow_id,
        "nodeId": s.node_id, "nodeType": s.node_type, "nodeName": s.node_name,
        "status": s.status, "inputData": s.input_data, "outputData": s.output_data,
        "errorMessage": s.error_message,
        "startedAt": s.started_at.isoformat() if s.started_at else None,
        "completedAt": s.completed_at.isoformat() if s.completed_at else None,
        "duration": s.duration, "retryCount": s.retry_count,
        "executionOrder": s.execution_order,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
    }


def _variable_to_dict(v: ExecutionVariable) -> dict:
    return {
        "id": v.id, "executionId": v.execution_id,
        "variableName": v.variable_name, "variableType": v.variable_type,
        "variableValue": v.variable_value, "isModified": v.is_modified,
        "createdAt": v.created_at.isoformat() if v.created_at else None,
        "updatedAt": v.updated_at.isoformat() if v.updated_at else None,
    }
