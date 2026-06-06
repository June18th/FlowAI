from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.common import Result
from app.schemas.workflow_version import (
    WorkflowVersionDiffResponse,
    WorkflowVersionResponse,
    WorkflowVersionRollbackResponse,
)
from app.services.workflow_service import workflow_service
from app.services.workflow_version_service import workflow_version_service

router = APIRouter(prefix="/api/v1/workflows/{workflow_id}/versions", tags=["workflow-versions"])


@router.get("", response_model=Result[list[WorkflowVersionResponse]])
async def list_versions(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    wf = await workflow_service.get_by_id(db, workflow_id)
    if not wf:
        return Result.error("工作流不存在", code=404)
    versions = await workflow_version_service.list_versions(db, workflow_id)
    return Result.success(versions)


@router.get("/{version_id}", response_model=Result[WorkflowVersionResponse])
async def get_version(
    workflow_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    version = await workflow_version_service.get_version(db, workflow_id, version_id)
    if not version:
        return Result.error("版本不存在", code=404)
    return Result.success(version)


@router.get("/{version1_id}/{version2_id}/diff", response_model=Result[WorkflowVersionDiffResponse])
async def diff_versions(
    workflow_id: int,
    version1_id: int,
    version2_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    diff = await workflow_version_service.diff_versions(
        db, workflow_id, version1_id, version2_id
    )
    if not diff:
        return Result.error("版本不存在或不属于同一工作流", code=404)
    return Result.success(diff)


@router.post("/{version_id}/rollback", response_model=Result[WorkflowVersionRollbackResponse])
async def rollback_version(
    workflow_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await workflow_version_service.rollback_to_version(
        db, workflow_id, version_id
    )
    if not result:
        return Result.error("版本不存在或工作流已删除", code=404)
    return Result.success(result, "回滚成功")
