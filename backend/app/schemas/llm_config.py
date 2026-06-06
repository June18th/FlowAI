from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class LLMGlobalConfigResponse(BaseModel):
    id: int
    provider: str
    configName: str
    apiUrl: str
    apiKey: str
    model: str
    ttsModel: str | None = None
    embeddingModel: str | None = None
    imageModel: str | None = None
    videoModel: str | None = None
    memoryEnabled: int | None = 0
    temperature: float = 0.7
    isDefault: int | None = 0
    createdAt: str | None = None
    updatedAt: str | None = None


class LLMGlobalConfigRequest(BaseModel):
    id: int | None = None
    provider: str = Field(..., min_length=1)
    configName: str = Field(..., min_length=1)
    apiUrl: str = Field(..., min_length=1)
    apiKey: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    ttsModel: str | None = None
    embeddingModel: str | None = None
    imageModel: str | None = None
    videoModel: str | None = None
    memoryEnabled: int | None = 0
    temperature: float | None = 0.7
    isDefault: int | None = 0


class LLMConfigPatchRequest(BaseModel):
    isDefault: int | None = None
