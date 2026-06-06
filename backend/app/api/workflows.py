from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.common import PageData, Result
from app.schemas.workflow import WorkflowRequest, WorkflowResponse
from app.services.workflow_service import workflow_service

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.post("", response_model=Result[WorkflowResponse])
async def create_workflow(req: WorkflowRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await workflow_service.create(db, req)
    return Result.success(result, "创建工作流成功")


@router.put("/{workflow_id}", response_model=Result[WorkflowResponse])
async def update_workflow(workflow_id: int, req: WorkflowRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await workflow_service.update(db, workflow_id, req)
    if result is None:
        return Result.error("工作流不存在", code=404)
    return Result.success(result, "更新工作流成功")


@router.delete("/{workflow_id}", response_model=Result[None])
async def delete_workflow(workflow_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    ok = await workflow_service.delete(db, workflow_id)
    if not ok:
        return Result.error("工作流不存在", code=404)
    return Result.success(message="删除工作流成功")


@router.get("/{workflow_id}", response_model=Result[WorkflowResponse])
async def get_workflow(workflow_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await workflow_service.get_by_id(db, workflow_id)
    if result is None:
        return Result.error("工作流不存在", code=404)
    return Result.success(result)


@router.get("", response_model=Result[PageData[WorkflowResponse]])
async def list_workflows(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await workflow_service.list_paginated(db, page, size)
    return Result.success(result)
