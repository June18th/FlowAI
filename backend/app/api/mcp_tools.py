from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.common import Result
from app.schemas.mcp_tools import (
    McpToolConfigRequest,
    McpToolConfigResponse,
    McpToolTestRequest,
)
from app.services.mcp_tool_service import mcp_tool_service

router = APIRouter(prefix="/api/v1/mcp-tools", tags=["mcp-tools"])


@router.get("", response_model=Result[list[McpToolConfigResponse]])
async def list_mcp_tools(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await mcp_tool_service.list_configs(db)
    return Result.success(result)


@router.post("", response_model=Result[McpToolConfigResponse])
async def create_mcp_tool(req: McpToolConfigRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    if req.toolType == "agent_plan_web_search" and req.env:
        result = await mcp_tool_service.create_agent_plan_web_search_from_request(db, req)
    else:
        result = await mcp_tool_service.create_config(db, req)
    return Result.success(result, "创建 MCP 工具成功")


@router.put("/{tool_id}", response_model=Result[McpToolConfigResponse])
async def update_mcp_tool(tool_id: int, req: McpToolConfigRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await mcp_tool_service.update_config(db, tool_id, req)
    if result is None:
        return Result.error("MCP 工具不存在", code=404)
    return Result.success(result, "更新 MCP 工具成功")


@router.delete("/{tool_id}", response_model=Result[None])
async def delete_mcp_tool(tool_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    ok = await mcp_tool_service.delete_config(db, tool_id)
    if not ok:
        return Result.error("MCP 工具不存在", code=404)
    return Result.success(message="删除 MCP 工具成功")


@router.post("/{tool_id}/actions/test", response_model=Result[dict])
async def test_mcp_tool(tool_id: int, req: McpToolTestRequest | None = None, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await mcp_tool_service.test_config(db, tool_id, req.query if req else None)
    if result is None:
        return Result.error("MCP 工具不存在", code=404)
    return Result.success(result)
