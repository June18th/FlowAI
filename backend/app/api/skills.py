from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import require_auth
from app.schemas.common import Result
from app.schemas.skills import SkillDetail, SkillSummary
from app.services.skill_service import skill_registry

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("", response_model=Result[list[SkillSummary]])
async def list_skills(_: str = Depends(require_auth)):
    result = skill_registry.get_all_summaries()
    return Result.success(result)


@router.get("/{name}", response_model=Result[SkillDetail])
async def get_skill(name: str, _: str = Depends(require_auth)):
    skill = skill_registry.get_skill(name)
    if skill is None:
        return Result.error("技能不存在", code=404)
    return Result.success(skill)


@router.get("/{skill_name}/references/{reference_name}", response_model=Result[str])
async def get_skill_reference(skill_name: str, reference_name: str, _: str = Depends(require_auth)):
    content = skill_registry.get_reference(skill_name, reference_name)
    if content is None:
        return Result.error("引用文档不存在", code=404)
    return Result.success(content)
