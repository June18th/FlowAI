from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_config import LLMGlobalConfig
from app.schemas.llm_config import LLMGlobalConfigRequest, LLMGlobalConfigResponse


def _to_response(cfg: LLMGlobalConfig) -> LLMGlobalConfigResponse:
    return LLMGlobalConfigResponse(
        id=cfg.id,
        provider=cfg.provider,
        configName=cfg.config_name,
        apiUrl=cfg.api_url,
        apiKey=cfg.api_key,
        model=cfg.model,
        ttsModel=cfg.tts_model,
        embeddingModel=cfg.embedding_model,
        imageModel=cfg.image_model,
        videoModel=cfg.video_model,
        memoryEnabled=cfg.memory_enabled,
        temperature=float(cfg.temperature),
        isDefault=cfg.is_default,
        createdAt=cfg.created_at.isoformat() if cfg.created_at else None,
        updatedAt=cfg.updated_at.isoformat() if cfg.updated_at else None,
    )


class LLMGlobalConfigService:
    @staticmethod
    def _canonicalize_provider(provider: str) -> str:
        mapping = {
            "open ai": "openai", "deep seek": "deepseek",
            "通义千问": "qwen", "阶跃星辰": "step", "智谱": "zhipu",            "火山方舟": "volcengine_agent_plan", "ark": "volcengine_agent_plan",
            "agent_plan": "volcengine_agent_plan",
        }
        return mapping.get(provider.lower(), provider.lower())

    async def list_by_provider(self, db: AsyncSession, provider: str) -> list[LLMGlobalConfigResponse]:
        provider = self._canonicalize_provider(provider)
        stmt = (
            select(LLMGlobalConfig)
            .where(LLMGlobalConfig.provider == provider, LLMGlobalConfig.deleted == 0)
            .order_by(LLMGlobalConfig.is_default.desc(), LLMGlobalConfig.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [_to_response(c) for c in result.scalars().all()]

    async def list_all(self, db: AsyncSession) -> list[LLMGlobalConfigResponse]:
        stmt = (
            select(LLMGlobalConfig)
            .where(LLMGlobalConfig.deleted == 0)
            .order_by(LLMGlobalConfig.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [_to_response(c) for c in result.scalars().all()]

    async def get_by_id(self, db: AsyncSession, config_id: int) -> LLMGlobalConfigResponse | None:
        cfg = await db.get(LLMGlobalConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return None
        return _to_response(cfg)

    async def get_default_config(self, db: AsyncSession, provider: str) -> LLMGlobalConfigResponse | None:
        provider = self._canonicalize_provider(provider)
        stmt = select(LLMGlobalConfig).where(
            LLMGlobalConfig.provider == provider,
            LLMGlobalConfig.is_default == 1,
            LLMGlobalConfig.deleted == 0,
        )
        result = await db.execute(stmt)
        cfg = result.scalar_one_or_none()
        return _to_response(cfg) if cfg else None

    async def save_config(self, db: AsyncSession, req: LLMGlobalConfigRequest) -> LLMGlobalConfigResponse:
        provider = self._canonicalize_provider(req.provider)

        if req.id:
            cfg = await db.get(LLMGlobalConfig, req.id)
            if cfg:
                cfg.provider = provider
                cfg.config_name = req.configName
                cfg.api_url = req.apiUrl
                cfg.api_key = req.apiKey
                cfg.model = req.model
                cfg.tts_model = req.ttsModel
                cfg.embedding_model = req.embeddingModel
                cfg.image_model = req.imageModel
                cfg.video_model = req.videoModel
                cfg.memory_enabled = req.memoryEnabled or 0
                cfg.temperature = Decimal(str(req.temperature or 0.7))
                cfg.is_default = req.isDefault or 0
                await db.flush()
                await db.refresh(cfg)
                return _to_response(cfg)

        # Check duplicate
        stmt = select(LLMGlobalConfig).where(
            LLMGlobalConfig.provider == provider,
            LLMGlobalConfig.config_name == req.configName,
            LLMGlobalConfig.deleted == 0,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return _to_response(existing)

        cfg = LLMGlobalConfig(
            provider=provider,
            config_name=req.configName,
            api_url=req.apiUrl,
            api_key=req.apiKey,
            model=req.model,
            tts_model=req.ttsModel,
            embedding_model=req.embeddingModel,
            image_model=req.imageModel,
            video_model=req.videoModel,
            memory_enabled=req.memoryEnabled or 0,
            temperature=Decimal(str(req.temperature or 0.7)),
            is_default=req.isDefault or 0,
        )
        db.add(cfg)
        await db.flush()
        await db.refresh(cfg)

        # Auto-set as default if first for provider
        count_stmt = select(LLMGlobalConfig).where(
            LLMGlobalConfig.provider == provider,
            LLMGlobalConfig.deleted == 0,
            LLMGlobalConfig.is_default == 1,
        )
        count_result = await db.execute(count_stmt)
        if count_result.scalar_one_or_none() is None:
            cfg.is_default = 1
            await db.flush()
            await db.refresh(cfg)

        return _to_response(cfg)

    async def delete_config(self, db: AsyncSession, config_id: int) -> bool:
        cfg = await db.get(LLMGlobalConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return False
        cfg.deleted = 1
        await db.flush()
        return True

    async def set_default_config(self, db: AsyncSession, config_id: int) -> bool:
        cfg = await db.get(LLMGlobalConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return False

        # Clear other defaults for this provider
        await db.execute(
            update(LLMGlobalConfig)
            .where(LLMGlobalConfig.provider == cfg.provider, LLMGlobalConfig.deleted == 0)
            .values(is_default=0)
        )

        cfg.is_default = 1
        await db.flush()
        return True

    async def get_raw_config(self, db: AsyncSession, config_id: int) -> LLMGlobalConfig | None:
        """Get raw entity for engine use."""
        cfg = await db.get(LLMGlobalConfig, config_id)
        if not cfg or cfg.deleted == 1:
            return None
        return cfg


llm_config_service = LLMGlobalConfigService()
