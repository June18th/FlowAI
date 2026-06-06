from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_auth
from app.schemas.common import Result
from app.schemas.knowledge import (
    KnowledgeBaseRequest,
    KnowledgePreviewRequest,
    KnowledgeSearchRequest,
    KnowledgeTextImportRequest,
)
from app.services.knowledge_service import knowledge_service

router = APIRouter(prefix="/api/v1/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=Result[list[dict]])
async def list_knowledge_bases(db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.list_knowledge_bases(db)
    return Result.success(result)


@router.post("", response_model=Result[dict])
async def create_knowledge_base(req: KnowledgeBaseRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.create_knowledge_base(db, req)
    return Result.success(result, "创建知识库成功")


@router.get("/{kb_id}", response_model=Result[dict])
async def get_knowledge_base(kb_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.get_knowledge_base(db, kb_id)
    if result is None:
        return Result.error("知识库不存在", code=404)
    return Result.success(result)


@router.delete("/{kb_id}", response_model=Result[None])
async def delete_knowledge_base(kb_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    ok = await knowledge_service.delete_knowledge_base(db, kb_id)
    if not ok:
        return Result.error("知识库不存在", code=404)
    return Result.success(message="删除知识库成功")


@router.post("/{kb_id}/documents/text", response_model=Result[dict])
async def import_text(kb_id: int, req: KnowledgeTextImportRequest, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.import_text(db, kb_id, req.title, req.content, req.tags)
    if result is None:
        return Result.error("知识库不存在", code=404)
    return Result.success(result, "导入文本成功")


@router.post("/{kb_id}/documents/upload", response_model=Result[dict])
async def upload_file(kb_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    filename = file.filename or "untitled"
    if not filename.endswith((".txt", ".md", ".markdown")):
        return Result.error("仅支持 .txt, .md, .markdown 文件", code=400)

    content = (await file.read()).decode("utf-8")
    result = await knowledge_service.upload_text_file(db, kb_id, filename, content)
    if result is None:
        return Result.error("知识库不存在", code=404)
    return Result.success(result, "上传文件成功")


@router.get("/{kb_id}/documents", response_model=Result[list[dict]])
async def list_documents(kb_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.list_documents(db, kb_id)
    return Result.success(result)


@router.post("/{kb_id}/documents/{doc_id}/preview-chunks", response_model=Result[list[dict]])
async def preview_chunks(kb_id: int, doc_id: int, req: KnowledgePreviewRequest | None = None, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.preview_chunks(
        db, kb_id, doc_id,
        req.chunkSize if req else None,
        req.chunkOverlap if req else None,
    )
    if result is None:
        return Result.error("文档不存在", code=404)
    return Result.success(result)


@router.post("/{kb_id}/documents/{doc_id}/index", response_model=Result[dict])
async def index_document(kb_id: int, doc_id: int, db: AsyncSession = Depends(get_db), _: str = Depends(require_auth)):
    result = await knowledge_service.index_document(db, kb_id, doc_id)
    if result is None:
        return Result.error("文档不存在", code=404)
    return Result.success(result, "索引任务创建成功")


@router.get("/{kb_id}/chunks", response_model=Result[dict])
async def search_knowledge_base(
    kb_id: int,
    query: str = Query(..., min_length=1),
    topK: int = Query(5),
    scoreThreshold: float = Query(0.5),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_auth),
):
    result = await knowledge_service.search(
        db, kb_id, query,
        top_k=topK,
        score_threshold=scoreThreshold,
    )
    return Result.success(result.model_dump())
