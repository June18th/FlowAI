from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.common import Result
from app.schemas.llm_config import LLMConfigPatchRequest, LLMGlobalConfigRequest, LLMGlobalConfigResponse
from app.services.llm_config_service import llm_config_service

router = APIRouter(prefix="/api/v1/llm-config", tags=["llm-config"])


@router.get("", response_model=Result[list[LLMGlobalConfigResponse]])
async def list_all_configs(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await llm_config_service.list_all(db)
    return Result.success(result)


@router.get("/{provider}", response_model=Result[list[LLMGlobalConfigResponse]])
async def list_by_provider(provider: str, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await llm_config_service.list_by_provider(db, provider)
    return Result.success(result)


@router.get("/detail/{config_id}", response_model=Result[LLMGlobalConfigResponse])
async def get_config_detail(config_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await llm_config_service.get_by_id(db, config_id)
    if result is None:
        return Result.error("配置不存在", code=404)
    return Result.success(result)


@router.get("/default/{provider}", response_model=Result[LLMGlobalConfigResponse])
async def get_default_config(provider: str, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await llm_config_service.get_default_config(db, provider)
    if result is None:
        return Result.error("未找到默认配置", code=404)
    return Result.success(result)


@router.post("", response_model=Result[LLMGlobalConfigResponse])
async def save_config(req: LLMGlobalConfigRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await llm_config_service.save_config(db, req)
    return Result.success(result, "保存配置成功")


@router.delete("/{config_id}", response_model=Result[None])
async def delete_config(config_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    ok = await llm_config_service.delete_config(db, config_id)
    if not ok:
        return Result.error("配置不存在", code=404)
    return Result.success(message="删除配置成功")


@router.patch("/{config_id}", response_model=Result[None])
async def update_config_partial(
    config_id: int,
    req: LLMConfigPatchRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    if req.isDefault:
        ok = await llm_config_service.set_default_config(db, config_id)
        if not ok:
            return Result.error("配置不存在", code=404)
        return Result.success(message="已设为默认")
    return Result.error("无变更", code=400)
