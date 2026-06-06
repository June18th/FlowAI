from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.database import async_session
from app.logging_config import logger
from app.models.execution import ExecutionRecord

ORPHAN_THRESHOLD_SECONDS = 60
SCAN_INTERVAL_SECONDS = 30

_worker_id: str | None = None


def get_worker_id() -> str:
    global _worker_id
    if _worker_id is None:
        _worker_id = uuid.uuid4().hex[:12]
    return _worker_id


async def run_recovery_worker(
    stop_event: asyncio.Event,
    auto_resume: bool = False,
    dag_engine=None,
    orphan_threshold_s: int = ORPHAN_THRESHOLD_SECONDS,
    scan_interval_s: int = SCAN_INTERVAL_SECONDS,
) -> None:
    logger.info(
        "recovery_worker.start",
        worker_id=get_worker_id(),
        orphan_threshold_s=orphan_threshold_s,
        auto_resume=auto_resume,
    )

    while not stop_event.is_set():
        try:
            async with async_session() as db:
                cutoff = datetime.utcnow() - timedelta(seconds=orphan_threshold_s)
                stmt = select(ExecutionRecord).where(
                    ExecutionRecord.status == "RUNNING",
                    ExecutionRecord.heartbeat_at.isnot(None),
                    ExecutionRecord.heartbeat_at < cutoff,
                    ExecutionRecord.engine_type == "dag",
                )
                result = await db.execute(stmt)
                orphans = result.scalars().all()

                for orphan in orphans:
                    logger.warning(
                        "recovery_worker.orphan_detected",
                        execution_id=orphan.id,
                        flow_id=orphan.flow_id,
                        worker_id=orphan.worker_id,
                        last_heartbeat=orphan.heartbeat_at.isoformat() if orphan.heartbeat_at else "never",
                        last_node=orphan.last_completed_node_id,
                    )
                    if auto_resume and dag_engine is not None and orphan.execution_state:
                        await _attempt_auto_resume(dag_engine, orphan, db)
        except Exception as e:
            logger.error("recovery_worker.error", error=str(e))

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=scan_interval_s)
        except asyncio.TimeoutError:
            pass

    logger.info("recovery_worker.stop")


async def _attempt_auto_resume(dag_engine, orphan: ExecutionRecord, db) -> None:
    try:
        from app.services.workflow_service import workflow_service

        wf = await workflow_service.get_workflow_entity(db, orphan.flow_id)
        if not wf:
            logger.error("recovery_worker.resume_fail.workflow_not_found", execution_id=orphan.id)
            return

        logger.info("recovery_worker.auto_resume", execution_id=orphan.id)
        orphan.worker_id = get_worker_id()
        orphan.heartbeat_at = datetime.utcnow()
        await db.commit()

        await dag_engine.execute(wf, "", db=db, resume_record=orphan)
    except Exception as e:
        logger.error("recovery_worker.auto_resume_failed", execution_id=orphan.id, error=str(e))
