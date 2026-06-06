from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.schemas.common import PageData
from app.schemas.workflow import WorkflowRequest, WorkflowResponse
from app.services.workflow_version_service import workflow_version_service


class WorkflowService:
    @staticmethod
    def _to_response(w: Workflow) -> WorkflowResponse:
        return WorkflowResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            flowData=w.flow_data,
            engineType=w.engine_type,
            createdAt=w.created_at.isoformat() if w.created_at else None,
            updatedAt=w.updated_at.isoformat() if w.updated_at else None,
        )

    async def create(self, db: AsyncSession, req: WorkflowRequest) -> WorkflowResponse:
        w = Workflow(
            name=req.name,
            description=req.description,
            flow_data=req.flowData,
            engine_type=req.engineType or "dag",
        )
        db.add(w)
        await db.flush()
        await db.refresh(w)
        return self._to_response(w)

    async def update(self, db: AsyncSession, workflow_id: int, req: WorkflowRequest) -> WorkflowResponse | None:
        w = await db.get(Workflow, workflow_id)
        if not w or w.deleted == 1:
            return None
        # Snapshot current state as a new version before mutation
        await workflow_version_service.create_version(db, w)
        w.name = req.name
        w.description = req.description
        w.flow_data = req.flowData
        w.engine_type = req.engineType or "dag"
        await db.flush()
        await db.refresh(w)
        return self._to_response(w)

    async def delete(self, db: AsyncSession, workflow_id: int) -> bool:
        w = await db.get(Workflow, workflow_id)
        if not w or w.deleted == 1:
            return False
        w.deleted = 1
        await db.flush()
        return True

    async def get_by_id(self, db: AsyncSession, workflow_id: int) -> WorkflowResponse | None:
        w = await db.get(Workflow, workflow_id)
        if not w or w.deleted == 1:
            return None
        return self._to_response(w)

    async def list_all(self, db: AsyncSession) -> list[WorkflowResponse]:
        stmt = (
            select(Workflow)
            .where(Workflow.deleted == 0)
            .order_by(Workflow.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [self._to_response(w) for w in result.scalars().all()]

    async def list_paginated(self, db: AsyncSession, page: int = 1, size: int = 20) -> PageData[WorkflowResponse]:
        base = select(Workflow).where(Workflow.deleted == 0)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        items_stmt = (
            select(Workflow)
            .where(Workflow.deleted == 0)
            .order_by(Workflow.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(items_stmt)
        items = [self._to_response(w) for w in result.scalars().all()]

        return PageData(items=items, total=total, page=page, size=size)

    async def get_workflow_entity(self, db: AsyncSession, workflow_id: int) -> Workflow | None:
        """Get raw Workflow entity (for engine use)."""
        w = await db.get(Workflow, workflow_id)
        if not w or w.deleted == 1:
            return None
        return w


workflow_service = WorkflowService()
