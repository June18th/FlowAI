from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeBaseRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    configId: int | None = None
    embeddingModel: str | None = None
    chunkSize: int | None = 800
    chunkOverlap: int | None = 100


class KnowledgeTextImportRequest(BaseModel):
    title: str | None = None
    content: str = Field(..., min_length=1)
    tags: str | None = None


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    topK: int | None = 5
    scoreThreshold: float | None = 0.5


class KnowledgePreviewRequest(BaseModel):
    chunkSize: int | None = None
    chunkOverlap: int | None = None


class KnowledgeChunkPreview(BaseModel):
    chunkIndex: int
    content: str
    charCount: int


class KnowledgeSearchResultItem(BaseModel):
    chunkId: int
    knowledgeBaseId: int
    documentId: int | None = None
    title: str | None = None
    content: str
    score: float


class KnowledgeSearchResult(BaseModel):
    chunks: list[KnowledgeSearchResultItem] = []
    citations: list[int] = []
    context: str = ""
