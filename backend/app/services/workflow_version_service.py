from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.models.workflow_version import WorkflowVersion
from app.schemas.workflow_version import (
    WorkflowVersionDiffResponse,
    WorkflowVersionResponse,
    WorkflowVersionRollbackResponse,
)


class WorkflowVersionService:
    @staticmethod
    def _to_response(v: WorkflowVersion) -> WorkflowVersionResponse:
        return WorkflowVersionResponse(
            id=v.id,
            workflowId=v.workflow_id,
            versionNumber=v.version_number,
            name=v.name,
            flowData=v.flow_data,
            engineType=v.engine_type,
            createdAt=v.created_at.isoformat() if v.created_at else None,
        )

    async def create_version(self, db: AsyncSession, workflow: Workflow) -> WorkflowVersionResponse:
        latest = await self.get_latest_version_number(db, workflow.id)
        version_number = latest + 1
        v = WorkflowVersion(
            workflow_id=workflow.id,
            version_number=version_number,
            name=workflow.name,
            flow_data=workflow.flow_data,
            engine_type=workflow.engine_type or "dag",
        )
        db.add(v)
        await db.flush()
        await db.refresh(v)
        return self._to_response(v)

    async def get_latest_version_number(self, db: AsyncSession, workflow_id: int) -> int:
        stmt = select(func.max(WorkflowVersion.version_number)).where(
            WorkflowVersion.workflow_id == workflow_id
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def list_versions(self, db: AsyncSession, workflow_id: int) -> list[WorkflowVersionResponse]:
        stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
        )
        result = await db.execute(stmt)
        return [self._to_response(v) for v in result.scalars().all()]

    async def get_version(self, db: AsyncSession, workflow_id: int, version_id: int) -> WorkflowVersionResponse | None:
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id,
        )
        result = await db.execute(stmt)
        v = result.scalar_one_or_none()
        if not v:
            return None
        return self._to_response(v)

    async def diff_versions(
        self, db: AsyncSession, workflow_id: int, version1_id: int, version2_id: int
    ) -> WorkflowVersionDiffResponse | None:
        v1 = await db.get(WorkflowVersion, version1_id)
        v2 = await db.get(WorkflowVersion, version2_id)
        if not v1 or not v2 or v1.workflow_id != workflow_id or v2.workflow_id != workflow_id:
            return None

        nodes1 = {n["id"]: n for n in (v1.flow_data.get("nodes") or [])}
        nodes2 = {n["id"]: n for n in (v2.flow_data.get("nodes") or [])}
        ids1 = set(nodes1.keys())
        ids2 = set(nodes2.keys())

        nodes_added = sorted(ids2 - ids1)
        nodes_removed = sorted(ids1 - ids2)
        nodes_modified = sorted(
            nid for nid in (ids1 & ids2) if nodes1[nid] != nodes2[nid]
        )

        edges1 = v1.flow_data.get("edges") or []
        edges2 = v2.flow_data.get("edges") or []
        edges_added = max(0, len(edges2) - len(edges1))
        edges_removed = max(0, len(edges1) - len(edges2))

        return WorkflowVersionDiffResponse(
            version1Id=v1.id,
            version1Number=v1.version_number,
            version2Id=v2.id,
            version2Number=v2.version_number,
            nameChanged=v1.name != v2.name,
            engineTypeChanged=v1.engine_type != v2.engine_type,
            nodesAdded=nodes_added,
            nodesRemoved=nodes_removed,
            nodesModified=nodes_modified,
            edgesAdded=edges_added,
            edgesRemoved=edges_removed,
        )

    async def rollback_to_version(
        self, db: AsyncSession, workflow_id: int, version_id: int
    ) -> WorkflowVersionRollbackResponse | None:
        target_version = await db.get(WorkflowVersion, version_id)
        if not target_version or target_version.workflow_id != workflow_id:
            return None

        workflow = await db.get(Workflow, workflow_id)
        if not workflow or workflow.deleted == 1:
            return None

        # Create a new version from current state first (preserve history)
        await self.create_version(db, workflow)

        # Apply the rollback
        workflow.name = target_version.name
        workflow.flow_data = target_version.flow_data
        workflow.engine_type = target_version.engine_type
        await db.flush()
        await db.refresh(workflow)

        # Create the rolled-back version
        rolled_back = await self.create_version(db, workflow)

        return WorkflowVersionRollbackResponse(
            workflowId=workflow.id,
            rolledFromVersion=target_version.version_number,
            rolledToVersion=rolled_back.version_number,
            newVersionNumber=rolled_back.version_number,
        )


workflow_version_service = WorkflowVersionService()
