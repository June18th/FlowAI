from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.workflow import NodeDefinition
from app.schemas.common import Result
from app.schemas.workflow import NodeDefinitionResponse

router = APIRouter(prefix="/api/v1/node-types", tags=["node-types"])

# Node types hidden from standalone listing
HIDDEN_TYPES = {
    "react_agent", "web_search", "web_fetch", "vision_analyze",
    "memory_write", "memory_retrieve", "knowledge_upsert", "knowledge_retrieve",
    "weather",  # legacy alias, use weather_query instead
}

# Additional synthesized node types (not in DB)
SYNTHETIC_TYPES = [
    {"node_type": "llm", "display_name": "LLM Node", "category": "LLM", "icon": "🤖",
     "input_schema": '{"type":"object","properties":{"input":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"output":{"type":"string"},"tokens":{"type":"number"}}}',
     "config_schema": '{"type":"object","properties":{"provider":{"type":"string"},"configId":{"type":"number"},"prompt":{"type":"string"},"temperature":{"type":"number","default":0.7}}}'},
    {"node_type": "memory_write", "display_name": "Memory Write", "category": "MEMORY", "icon": "🧠",
     "input_schema": '{"type":"object","properties":{"content":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"memoryId":{"type":"string"}}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "memory_retrieve", "display_name": "Memory Retrieve", "category": "MEMORY", "icon": "🔍",
     "input_schema": '{"type":"object","properties":{"query":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"memories":{"type":"array"}}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "knowledge_upsert", "display_name": "Knowledge Upsert", "category": "KNOWLEDGE", "icon": "📚",
     "input_schema": '{"type":"object","properties":{"content":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "knowledge_retrieve", "display_name": "Knowledge Retrieve", "category": "KNOWLEDGE", "icon": "🔎",
     "input_schema": '{"type":"object","properties":{"query":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"chunks":{"type":"array"}}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "image_generate", "display_name": "Image Generate", "category": "TOOL", "icon": "🖼️",
     "input_schema": '{"type":"object","properties":{"prompt":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"imageUrl":{"type":"string"}}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "video_generate", "display_name": "Video Generate", "category": "TOOL", "icon": "🎬",
     "input_schema": '{"type":"object","properties":{"prompt":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"videoUrl":{"type":"string"}}}',
     "config_schema": '{"type":"object","properties":{}}'},
    {"node_type": "tts", "display_name": "TTS 语音合成", "category": "TOOL", "icon": "🗣️",
     "input_schema": '{"type":"object","properties":{"text":{"type":"string"},"provider":{"type":"string","default":"qwen"}}}',
     "output_schema": '{"type":"object","properties":{"audioUrl":{"type":"string"},"duration":{"type":"number"}}}',
     "config_schema": '{"type":"object","properties":{"provider":{"type":"string","default":"qwen"}}}'},
    {"node_type": "weather_query", "display_name": "天气查询", "category": "TOOL", "icon": "🌤️",
     "input_schema": '{"type":"object","properties":{"city":{"type":"string"}}}',
     "output_schema": '{"type":"object","properties":{"city":{"type":"string"},"live":{"type":"object"},"forecasts":{"type":"array"},"forecastSummary":{"type":"string"}}}',
     "config_schema": '{"type":"object","properties":{"apiKey":{"type":"string","description":"高德地图 API Key"}}}'},
]


def _to_response(nd: NodeDefinition) -> NodeDefinitionResponse:
    return NodeDefinitionResponse(
        id=nd.id,
        nodeType=nd.node_type,
        displayName=nd.display_name,
        category=nd.category,
        icon=nd.icon,
        inputSchema=nd.input_schema,
        outputSchema=nd.output_schema,
        configSchema=nd.config_schema,
    )


async def _get_all_node_types(db: AsyncSession) -> list[NodeDefinitionResponse]:
    stmt = select(NodeDefinition).where(NodeDefinition.deleted == 0)
    result = await db.execute(stmt)
    definitions = list(result.scalars().all())

    # Filter hidden types
    filtered = [d for d in definitions if d.node_type not in HIDDEN_TYPES]

    # Remove individual LLM provider types, keep only synthesized "llm"
    llm_providers = {"openai", "deepseek", "qwen", "step", "zhipu"}
    filtered = [d for d in filtered if d.node_type not in llm_providers]

    responses = [_to_response(d) for d in filtered]
    existing_types = {r.nodeType for r in responses}

    # Add synthesized types (skip if already in DB)
    for synth in SYNTHETIC_TYPES:
        if synth["node_type"] in existing_types:
            continue
        responses.append(NodeDefinitionResponse(
            id=0,
            nodeType=synth["node_type"],
            displayName=synth["display_name"],
            category=synth["category"],
            icon=synth["icon"],
            inputSchema=synth["input_schema"],
            outputSchema=synth["output_schema"],
            configSchema=synth["config_schema"],
        ))

    return responses


@router.get("", response_model=Result[list[NodeDefinitionResponse]])
async def get_node_types(db: AsyncSession = Depends(get_db)):
    result = await _get_all_node_types(db)
    return Result.success(result)


async def get_node_definition_by_type(db: AsyncSession, node_type: str) -> NodeDefinition | None:
    """Get a single node definition by type (for engine use)."""
    stmt = select(NodeDefinition).where(
        NodeDefinition.node_type == node_type,
        NodeDefinition.deleted == 0,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
