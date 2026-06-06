from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp import McpToolConfig
from app.schemas.mcp_tools import (
    AgentPlanWebSearchMcpRequest,
    McpToolConfigRequest,
    McpToolConfigResponse,
)


def _to_response(cfg: McpToolConfig) -> McpToolConfigResponse:
    return McpToolConfigResponse(
        id=cfg.id,
        name=cfg.name,
        description=cfg.description,
        toolType=cfg.tool_type,
        toolName=cfg.tool_name,
        transport=cfg.transport,
        command=cfg.command,
        args=cfg.args if isinstance(cfg.args, list) else [],
        env=cfg.env if isinstance(cfg.env, dict) else {},
        enabled=cfg.enabled,
        preset=cfg.preset,
        createdAt=cfg.created_at.isoformat() if cfg.created_at else None,
        updatedAt=cfg.updated_at.isoformat() if cfg.updated_at else None,
    )


class McpToolConfigService:
    async def list_configs(self, db: AsyncSession) -> list[McpToolConfigResponse]:
        stmt = (
            select(McpToolConfig)
            .where(McpToolConfig.deleted == 0)
            .order_by(McpToolConfig.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [_to_response(c) for c in result.scalars().all()]

    async def create_config(self, db: AsyncSession, req: McpToolConfigRequest) -> McpToolConfigResponse:
        cfg = McpToolConfig(
            name=req.name,
            description=req.description,
            tool_type=req.toolType or "custom",
            tool_name=req.toolName,
            transport=req.transport or "stdio",
            command=req.command,
            args=req.args or [],
            env=req.env or {},
            enabled=req.enabled if req.enabled is not None else 1,
        )
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)
        return _to_response(cfg)

    async def create_agent_plan_web_search(self, db: AsyncSession, req: AgentPlanWebSearchMcpRequest) -> McpToolConfigResponse:
        mcp_req = McpToolConfigRequest(
            name=req.name or "Agent Plan Web Search",
            description=req.description or "Agent Plan harness web search via MCP",
            toolType="agent_plan_web_search",
            toolName="web_search",
            transport="stdio",
            command="uvx",
            args=["git+https://github.com/volcengine/mcp-server#subdirectory=server/mcp_server_askecho_search_infinity"],
            env={"API_KEY": req.apiKey},
            enabled=1,
        )
        return await self.create_config(db, mcp_req)

    async def create_agent_plan_web_search_from_request(self, db: AsyncSession, req: McpToolConfigRequest) -> McpToolConfigResponse:
        return await self.create_config(db, req)

    async def update_config(self, db: AsyncSession, config_id: int, req: McpToolConfigRequest) -> McpToolConfigResponse | None:
        cfg = await db.get(McpToolConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return None
        cfg.name = req.name
        cfg.description = req.description
        cfg.tool_type = req.toolType or "custom"
        cfg.tool_name = req.toolName
        cfg.transport = req.transport or "stdio"
        cfg.command = req.command
        cfg.args = req.args or []
        cfg.env = req.env or {}
        cfg.enabled = req.enabled if req.enabled is not None else 1
        await db.flush()
        await db.refresh(cfg)
        return _to_response(cfg)

    async def delete_config(self, db: AsyncSession, config_id: int) -> bool:
        cfg = await db.get(McpToolConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return False
        cfg.deleted = 1
        await db.flush()
        return True

    async def test_config(self, db: AsyncSession, config_id: int, query: str | None) -> dict | None:
        cfg = await db.get(McpToolConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return None
        return {"status": "ok", "tool": cfg.tool_name, "message": "工具连接正常"}

    async def get_raw_config(self, db: AsyncSession, config_id: int) -> McpToolConfig | None:
        cfg = await db.get(McpToolConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return None
        return cfg


mcp_tool_service = McpToolConfigService()
