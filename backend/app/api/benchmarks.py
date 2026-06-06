from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.benchmark import (
    BenchmarkCaseRequest,
    BenchmarkCaseResponse,
    BenchmarkDatasetRequest,
    BenchmarkDatasetResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)
from app.schemas.common import PageData, Result
from app.services.benchmark_service import benchmark_service

router = APIRouter(prefix="/api/v1/benchmarks", tags=["benchmarks"])


# ── Datasets ──

@router.post("/datasets", response_model=Result[BenchmarkDatasetResponse])
async def create_dataset(
    req: BenchmarkDatasetRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.create_dataset(db, req)
    return Result.success(result, "创建数据集成功")


@router.get("/datasets", response_model=Result[PageData[BenchmarkDatasetResponse]])
async def list_datasets(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.list_datasets(db, page, size)
    return Result.success(result)


@router.get("/datasets/{dataset_id}", response_model=Result[BenchmarkDatasetResponse])
async def get_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.get_dataset(db, dataset_id)
    if not result:
        return Result.error("数据集不存在", code=404)
    return Result.success(result)


@router.put("/datasets/{dataset_id}", response_model=Result[BenchmarkDatasetResponse])
async def update_dataset(
    dataset_id: int,
    req: BenchmarkDatasetRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.update_dataset(db, dataset_id, req)
    if not result:
        return Result.error("数据集不存在", code=404)
    return Result.success(result, "更新数据集成功")


@router.delete("/datasets/{dataset_id}", response_model=Result[None])
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    ok = await benchmark_service.delete_dataset(db, dataset_id)
    if not ok:
        return Result.error("数据集不存在", code=404)
    return Result.success(None, "删除数据集成功")


# ── Cases ──

@router.post("/datasets/{dataset_id}/cases", response_model=Result[BenchmarkCaseResponse])
async def add_case(
    dataset_id: int,
    req: BenchmarkCaseRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.add_case(db, dataset_id, req)
    if not result:
        return Result.error("数据集不存在", code=404)
    return Result.success(result, "添加用例成功")


@router.post("/datasets/{dataset_id}/cases/bulk", response_model=Result[dict])
async def bulk_add_cases(
    dataset_id: int,
    cases: list[BenchmarkCaseRequest],
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    count = await benchmark_service.bulk_add_cases(db, dataset_id, cases)
    if count is None:
        return Result.error("数据集不存在", code=404)
    return Result.success({"count": count}, f"批量添加 {count} 个用例成功")


@router.get("/datasets/{dataset_id}/cases", response_model=Result[list[BenchmarkCaseResponse]])
async def list_cases(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.list_cases(db, dataset_id)
    if result is None:
        return Result.error("数据集不存在", code=404)
    return Result.success(result)


@router.put("/cases/{case_id}", response_model=Result[BenchmarkCaseResponse])
async def update_case(
    case_id: int,
    req: BenchmarkCaseRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.update_case(db, case_id, req)
    if not result:
        return Result.error("用例不存在", code=404)
    return Result.success(result, "更新用例成功")


@router.delete("/cases/{case_id}", response_model=Result[None])
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    ok = await benchmark_service.delete_case(db, case_id)
    if not ok:
        return Result.error("用例不存在", code=404)
    return Result.success(None, "删除用例成功")


# ── Benchmark execution ──

@router.post("/datasets/{dataset_id}/run", response_model=Result[BenchmarkRunResponse])
async def run_benchmark(
    dataset_id: int,
    req: BenchmarkRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.run_benchmark(
        db, dataset_id,
        workflow_id_override=req.workflowId if req else None,
        judge_config_id=req.judgeConfigId if req else None,
    )
    if not result:
        return Result.error("数据集不存在或无关联工作流", code=404)
    return Result.success(result, "Benchmark 执行完成")


# ── Results ──

@router.get("/datasets/{dataset_id}/runs", response_model=Result[list[BenchmarkRunResponse]])
async def list_runs(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.list_runs(db, dataset_id)
    if result is None:
        return Result.error("数据集不存在", code=404)
    return Result.success(result)


@router.get("/runs/{run_id}", response_model=Result[BenchmarkRunResponse])
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await benchmark_service.get_run(db, run_id)
    if not result:
        return Result.error("Benchmark 执行记录不存在", code=404)
    return Result.success(result)
