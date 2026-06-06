from __future__ import annotations

import json
import time
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.engine.engine_selector import dag_engine
from app.models.benchmark import BenchmarkCase, BenchmarkDataset, BenchmarkRun
from app.schemas.benchmark import (
    BenchmarkCaseRequest,
    BenchmarkCaseResponse,
    BenchmarkDatasetRequest,
    BenchmarkDatasetResponse,
    BenchmarkRunResponse,
)
from app.schemas.common import PageData
from app.services.workflow_service import workflow_service


def _score_exact(actual: str, expected: str) -> float:
    return 1.0 if actual.strip() == expected.strip() else 0.0


def _score_contains(actual: str, expected: str) -> float:
    return 1.0 if expected.strip() in actual else 0.0


def _score_semantic(actual: str, expected: str) -> float:
    """Simple word-overlap based similarity as a heuristic."""
    actual_words = set(actual.strip().lower().split())
    expected_words = set(expected.strip().lower().split())
    if not expected_words:
        return 0.0
    return len(actual_words & expected_words) / len(expected_words | actual_words)


async def _score_llm_judge(actual: str, expected: str, judge_config_id: int | None = None) -> float:
    """Use an LLM to judge output quality. Falls back to semantic on failure."""
    from app.engine.llm.chat_client_factory import create_chat_client
    from app.services.llm_config_service import llm_config_service

    try:
        from langchain_core.messages import HumanMessage

        config = None
        if judge_config_id:
            async with async_session() as session:
                config = await llm_config_service.get_raw_config(session, judge_config_id)
        if not config:
            async with async_session() as session:
                config_list = await llm_config_service.list_all(session)
                config = config_list[0] if config_list else None

        if not config:
            return _score_semantic(actual, expected)

        client = create_chat_client(
            provider=config.provider,
            api_url=config.api_url,
            api_key=config.api_key,
            model=config.model,
            temperature=0.0,
        )
        judge_prompt = (
            "Given the expected output and the actual output below, "
            "rate how well the actual output matches the expected output on a scale from 0.0 to 1.0. "
            "0.0 means completely different, 1.0 means perfect match. "
            "Consider factual accuracy, completeness, and relevance. "
            "Respond with ONLY the numeric score (e.g. 0.85), nothing else.\n\n"
            f"Expected output:\n{expected}\n\n"
            f"Actual output:\n{actual}"
        )
        response = await client.ainvoke([HumanMessage(content=judge_prompt)])
        score_str = response.content.strip()
        try:
            return max(0.0, min(1.0, float(score_str)))
        except ValueError:
            return _score_semantic(actual, expected)
    except Exception:
        return _score_semantic(actual, expected)


SCORING_METHODS = {
    "exact": _score_exact,
    "contains": _score_contains,
    "semantic": _score_semantic,
    "llm_judge": _score_llm_judge,
}


class BenchmarkService:
    # ── Dataset CRUD ──

    @staticmethod
    def _dataset_to_response(d: BenchmarkDataset, case_count: int = 0) -> BenchmarkDatasetResponse:
        return BenchmarkDatasetResponse(
            id=d.id,
            name=d.name,
            description=d.description,
            workflowId=d.workflow_id,
            caseCount=case_count,
            createdAt=d.created_at.isoformat() if d.created_at else None,
            updatedAt=d.updated_at.isoformat() if d.updated_at else None,
        )

    @staticmethod
    def _case_to_response(c: BenchmarkCase) -> BenchmarkCaseResponse:
        return BenchmarkCaseResponse(
            id=c.id,
            datasetId=c.dataset_id,
            inputData=c.input_data,
            expectedOutput=c.expected_output,
            scoringMethod=c.scoring_method,
            createdAt=c.created_at.isoformat() if c.created_at else None,
        )

    @staticmethod
    def _run_to_response(r: BenchmarkRun) -> BenchmarkRunResponse:
        return BenchmarkRunResponse(
            id=r.id,
            datasetId=r.dataset_id,
            workflowId=r.workflow_id,
            totalCases=r.total_cases,
            passedCases=r.passed_cases,
            failedCases=r.failed_cases,
            avgScore=float(r.avg_score) if r.avg_score is not None else None,
            results=r.results or [],
            status=r.status,
            createdAt=r.created_at.isoformat() if r.created_at else None,
            completedAt=r.completed_at.isoformat() if r.completed_at else None,
        )

    async def create_dataset(self, db: AsyncSession, req: BenchmarkDatasetRequest) -> BenchmarkDatasetResponse:
        d = BenchmarkDataset(
            name=req.name,
            description=req.description,
            workflow_id=req.workflowId,
        )
        db.add(d)
        await db.flush()
        await db.refresh(d)
        return self._dataset_to_response(d)

    async def list_datasets(self, db: AsyncSession, page: int = 1, size: int = 20) -> PageData[BenchmarkDatasetResponse]:
        base = select(BenchmarkDataset).where(BenchmarkDataset.deleted == 0)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        items_stmt = (
            select(BenchmarkDataset)
            .where(BenchmarkDataset.deleted == 0)
            .order_by(BenchmarkDataset.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(items_stmt)
        datasets = result.scalars().all()

        items = []
        for d in datasets:
            case_count_stmt = select(func.count()).select_from(
                select(BenchmarkCase).where(BenchmarkCase.dataset_id == d.id, BenchmarkCase.deleted == 0).subquery()
            )
            case_count = (await db.execute(case_count_stmt)).scalar() or 0
            items.append(self._dataset_to_response(d, case_count))

        return PageData(items=items, total=total, page=page, size=size)

    async def get_dataset(self, db: AsyncSession, dataset_id: int) -> BenchmarkDatasetResponse | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        case_count_stmt = select(func.count()).select_from(
            select(BenchmarkCase).where(BenchmarkCase.dataset_id == d.id, BenchmarkCase.deleted == 0).subquery()
        )
        case_count = (await db.execute(case_count_stmt)).scalar() or 0
        return self._dataset_to_response(d, case_count)

    async def update_dataset(self, db: AsyncSession, dataset_id: int, req: BenchmarkDatasetRequest) -> BenchmarkDatasetResponse | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        d.name = req.name
        d.description = req.description
        d.workflow_id = req.workflowId
        await db.flush()
        await db.refresh(d)
        return self._dataset_to_response(d)

    async def delete_dataset(self, db: AsyncSession, dataset_id: int) -> bool:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return False
        d.deleted = 1
        # Also soft-delete cases and runs
        stmt_case = select(BenchmarkCase).where(BenchmarkCase.dataset_id == dataset_id, BenchmarkCase.deleted == 0)
        case_result = await db.execute(stmt_case)
        for c in case_result.scalars().all():
            c.deleted = 1
        stmt_run = select(BenchmarkRun).where(BenchmarkRun.dataset_id == dataset_id, BenchmarkRun.deleted == 0)
        run_result = await db.execute(stmt_run)
        for r in run_result.scalars().all():
            r.deleted = 1
        await db.flush()
        return True

    # ── Case CRUD ──

    async def add_case(self, db: AsyncSession, dataset_id: int, req: BenchmarkCaseRequest) -> BenchmarkCaseResponse | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        c = BenchmarkCase(
            dataset_id=dataset_id,
            input_data=req.inputData,
            expected_output=req.expectedOutput,
            scoring_method=req.scoringMethod,
        )
        db.add(c)
        await db.flush()
        await db.refresh(c)
        return self._case_to_response(c)

    async def bulk_add_cases(self, db: AsyncSession, dataset_id: int, cases: list[BenchmarkCaseRequest]) -> int | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        count = 0
        for req in cases:
            c = BenchmarkCase(
                dataset_id=dataset_id,
                input_data=req.inputData,
                expected_output=req.expectedOutput,
                scoring_method=req.scoringMethod,
            )
            db.add(c)
            count += 1
        await db.flush()
        return count

    async def list_cases(self, db: AsyncSession, dataset_id: int) -> list[BenchmarkCaseResponse] | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        stmt = (
            select(BenchmarkCase)
            .where(BenchmarkCase.dataset_id == dataset_id, BenchmarkCase.deleted == 0)
            .order_by(BenchmarkCase.id)
        )
        result = await db.execute(stmt)
        return [self._case_to_response(c) for c in result.scalars().all()]

    async def update_case(self, db: AsyncSession, case_id: int, req: BenchmarkCaseRequest) -> BenchmarkCaseResponse | None:
        c = await db.get(BenchmarkCase, case_id)
        if not c or c.deleted == 1:
            return None
        c.input_data = req.inputData
        c.expected_output = req.expectedOutput
        c.scoring_method = req.scoringMethod
        await db.flush()
        await db.refresh(c)
        return self._case_to_response(c)

    async def delete_case(self, db: AsyncSession, case_id: int) -> bool:
        c = await db.get(BenchmarkCase, case_id)
        if not c or c.deleted == 1:
            return False
        c.deleted = 1
        await db.flush()
        return True

    # ── Benchmark execution ──

    async def run_benchmark(
        self,
        db: AsyncSession,
        dataset_id: int,
        workflow_id_override: int | None = None,
        judge_config_id: int | None = None,
    ) -> BenchmarkRunResponse | None:
        dataset = await db.get(BenchmarkDataset, dataset_id)
        if not dataset or dataset.deleted == 1:
            return None

        workflow_id = workflow_id_override or dataset.workflow_id
        if not workflow_id:
            return None

        workflow_entity = await workflow_service.get_workflow_entity(db, workflow_id)
        if not workflow_entity:
            return None

        stmt = select(BenchmarkCase).where(BenchmarkCase.dataset_id == dataset_id, BenchmarkCase.deleted == 0)
        result = await db.execute(stmt)
        cases = result.scalars().all()

        if not cases:
            return None

        run = BenchmarkRun(
            dataset_id=dataset_id,
            workflow_id=workflow_id,
            total_cases=len(cases),
            status="RUNNING",
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)

        run_results = []
        total_score = 0.0
        passed = 0
        failed = 0

        for case in cases:
            case_start = time.monotonic()
            try:
                output = await dag_engine.execute(
                    workflow_entity, case.input_data, event_callback=None, db=db,
                )
                actual_output = json.dumps(output, ensure_ascii=False) if isinstance(output, dict) else str(output)

                scoring_method = case.scoring_method or "contains"
                score_fn = SCORING_METHODS.get(scoring_method, _score_contains)
                if scoring_method == "llm_judge":
                    score = await score_fn(actual_output, case.expected_output or "", judge_config_id)
                else:
                    score = score_fn(actual_output, case.expected_output or "")

                total_score += score
                if score >= 0.8:
                    passed += 1
                else:
                    failed += 1

                run_results.append({
                    "caseId": case.id,
                    "input": case.input_data[:500],
                    "expected": case.expected_output[:500] if case.expected_output else "",
                    "actual": actual_output[:500],
                    "score": round(score, 2),
                    "passed": score >= 0.8,
                    "durationMs": round((time.monotonic() - case_start) * 1000),
                })
            except Exception as exc:
                failed += 1
                run_results.append({
                    "caseId": case.id,
                    "input": case.input_data[:500],
                    "expected": case.expected_output[:500] if case.expected_output else "",
                    "actual": "",
                    "score": 0.0,
                    "passed": False,
                    "durationMs": round((time.monotonic() - case_start) * 1000),
                    "error": str(exc),
                })

        avg = total_score / len(cases) if cases else 0.0
        run.passed_cases = passed
        run.failed_cases = failed
        run.avg_score = round(avg, 2)
        run.results = run_results
        run.status = "COMPLETED"
        run.completed_at = datetime.utcnow()
        await db.flush()
        await db.refresh(run)

        return self._run_to_response(run)

    # ── Results ──

    async def list_runs(self, db: AsyncSession, dataset_id: int) -> list[BenchmarkRunResponse] | None:
        d = await db.get(BenchmarkDataset, dataset_id)
        if not d or d.deleted == 1:
            return None
        stmt = (
            select(BenchmarkRun)
            .where(BenchmarkRun.dataset_id == dataset_id, BenchmarkRun.deleted == 0)
            .order_by(BenchmarkRun.created_at.desc())
        )
        result = await db.execute(stmt)
        return [self._run_to_response(r) for r in result.scalars().all()]

    async def get_run(self, db: AsyncSession, run_id: int) -> BenchmarkRunResponse | None:
        r = await db.get(BenchmarkRun, run_id)
        if not r or r.deleted == 1:
            return None
        return self._run_to_response(r)


benchmark_service = BenchmarkService()
