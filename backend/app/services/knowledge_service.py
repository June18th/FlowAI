from __future__ import annotations

import math
import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeIndexTask
from app.schemas.knowledge import (
    KnowledgeBaseRequest,
    KnowledgeSearchResult,
    KnowledgeSearchResultItem,
)


class KnowledgeService:
    # ---------- helpers ----------

    @staticmethod
    def _split_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
        """Simple recursive character text splitter."""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            # Try to break at a natural boundary
            chunk = text[start:end]
            for sep in ["\n\n", "\n", "。", ".", " ", ""]:
                last = chunk.rfind(sep)
                if last > chunk_size // 2:
                    end = start + last + len(sep)
                    break

            chunks.append(text[start:end].strip())
            start = end - chunk_overlap if end - chunk_overlap > start else end

        return [c for c in chunks if c]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _text_relevance(text: str, query: str) -> float:
        """Simple text-based relevance scoring for Chinese/English."""
        if not query:
            return 0.0
        text_lower = text.lower()
        query_lower = query.lower()

        # Exact match
        if query_lower in text_lower:
            return 0.7

        # Bigram overlap for Chinese
        def bigrams(s: str) -> set:
            return {s[i:i + 2] for i in range(len(s) - 1)}

        query_bigrams = bigrams(query_lower)
        text_bigrams = bigrams(text_lower)
        if query_bigrams:
            overlap = len(query_bigrams & text_bigrams)
            return overlap / len(query_bigrams) * 0.5

        return 0.0

    @staticmethod
    def _token_count(text: str) -> int:
        """Estimate token count for Chinese text."""
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(re.findall(r"[a-zA-Z0-9]+", text))
        return chinese_chars + other_chars

    # ---------- Knowledge Base CRUD ----------

    async def list_knowledge_bases(self, db: AsyncSession) -> list[dict]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.deleted == 0)
            .order_by(KnowledgeBase.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [self._kb_to_dict(kb) for kb in result.scalars().all()]

    async def get_knowledge_base(self, db: AsyncSession, kb_id: int) -> dict | None:
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb or kb.deleted == 1:
            return None

        data = self._kb_to_dict(kb)

        # Include documents
        doc_stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_base_id == kb_id, KnowledgeDocument.deleted == 0)
            .order_by(KnowledgeDocument.updated_at.desc())
        )
        doc_result = await db.execute(doc_stmt)
        data["documents"] = [self._doc_to_dict(d) for d in doc_result.scalars().all()]

        # Include recent tasks
        task_stmt = (
            select(KnowledgeIndexTask)
            .where(KnowledgeIndexTask.knowledge_base_id == kb_id, KnowledgeIndexTask.deleted == 0)
            .order_by(KnowledgeIndexTask.updated_at.desc())
            .limit(10)
        )
        task_result = await db.execute(task_stmt)
        data["recentTasks"] = [self._task_to_dict(t) for t in task_result.scalars().all()]

        return data

    async def create_knowledge_base(self, db: AsyncSession, req: KnowledgeBaseRequest) -> dict:
        kb = KnowledgeBase(
            name=req.name,
            description=req.description,
            config_id=req.configId,
            embedding_model=req.embeddingModel,
            chunk_size=req.chunkSize or 800,
            chunk_overlap=req.chunkOverlap or 100,
        )
        db.add(kb)
        await db.flush()
        await db.refresh(kb)
        return self._kb_to_dict(kb)

    async def delete_knowledge_base(self, db: AsyncSession, kb_id: int) -> bool:
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb or kb.deleted == 1:
            return False


        await db.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.knowledge_base_id == kb_id)
            .values(deleted=1)
        )
        await db.execute(
            update(KnowledgeIndexTask)
            .where(KnowledgeIndexTask.knowledge_base_id == kb_id)
            .values(deleted=1)
        )
        await db.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_base_id == kb_id)
            .values(deleted=1)
        )

        kb.deleted = 1
        await db.flush()
        return True

    # ---------- Document Management ----------

    async def import_text(self, db: AsyncSession, kb_id: int, title: str | None, content: str, tags: str | None) -> dict | None:
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb or kb.deleted == 1:
            return None

        doc = KnowledgeDocument(
            knowledge_base_id=kb_id,
            title=title or "Untitled",
            source_type="TEXT",
            raw_text=content,
            tags=tags,
            char_count=len(content),
            status="IMPORTED",
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        # Update KB stats
        kb.document_count = (kb.document_count or 0) + 1
        kb.char_count = (kb.char_count or 0) + len(content)
        await db.flush()

        return self._doc_to_dict(doc)

    async def upload_text_file(self, db: AsyncSession, kb_id: int, filename: str, content: str) -> dict | None:
        kb = await db.get(KnowledgeBase, kb_id)
        if not kb or kb.deleted == 1:
            return None

        doc = KnowledgeDocument(
            knowledge_base_id=kb_id,
            title=filename,
            source_type="FILE",
            file_name=filename,
            raw_text=content,
            char_count=len(content),
            status="IMPORTED",
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        kb.document_count = (kb.document_count or 0) + 1
        kb.char_count = (kb.char_count or 0) + len(content)
        await db.flush()

        return self._doc_to_dict(doc)

    async def list_documents(self, db: AsyncSession, kb_id: int) -> list[dict]:
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_base_id == kb_id, KnowledgeDocument.deleted == 0)
            .order_by(KnowledgeDocument.updated_at.desc())
        )
        result = await db.execute(stmt)
        return [self._doc_to_dict(d) for d in result.scalars().all()]

    async def preview_chunks(self, db: AsyncSession, kb_id: int, doc_id: int, chunk_size: int | None, chunk_overlap: int | None) -> list[dict] | None:
        doc = await db.get(KnowledgeDocument, doc_id)
        if not doc or doc.deleted == 1 or doc.knowledge_base_id != kb_id:
            return None

        kb = await db.get(KnowledgeBase, kb_id)
        size = chunk_size or (kb.chunk_size if kb else 800)
        overlap = chunk_overlap or (kb.chunk_overlap if kb else 100)

        chunks = self._split_text(doc.raw_text or "", size, overlap)
        return [
            {"chunkIndex": i, "content": c, "charCount": len(c)}
            for i, c in enumerate(chunks)
        ]

    async def index_document(self, db: AsyncSession, kb_id: int, doc_id: int) -> dict | None:
        doc = await db.get(KnowledgeDocument, doc_id)
        if not doc or doc.deleted == 1 or doc.knowledge_base_id != kb_id:
            return None

        kb = await db.get(KnowledgeBase, kb_id)
        if not kb:
            return None

        # Create index task
        chunks = self._split_text(doc.raw_text or "", kb.chunk_size or 800, kb.chunk_overlap or 100)

        task = KnowledgeIndexTask(
            knowledge_base_id=kb_id,
            document_id=doc_id,
            status="RUNNING" if chunks else "COMPLETED",
            total_chunks=len(chunks),
            finished_chunks=0,
            progress=0,
        )
        db.add(task)
        await db.flush()

        # Create chunks (without embeddings for now)
        for i, chunk_text in enumerate(chunks):
            chunk = KnowledgeChunk(
                knowledge_base_id=kb_id,
                document_id=doc_id,
                chunk_index=i,
                title=doc.title,
                content=chunk_text,
                char_count=len(chunk_text),
                status="READY",
            )
            db.add(chunk)

        # Mark task complete
        task.status = "COMPLETED"
        task.finished_chunks = len(chunks)
        task.progress = 100

        # Update KB stats
        doc.status = "INDEXED"
        kb.chunk_count = (kb.chunk_count or 0) + len(chunks)
        kb.status = "READY"
        await db.flush()
        await db.refresh(task)

        return self._task_to_dict(task)

    # ---------- Search ----------

    async def search(self, db: AsyncSession, kb_id: int, query: str, top_k: int = 5, score_threshold: float = 0.5) -> dict:
        """Search knowledge base with text-based relevance scoring."""
        stmt = (
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.knowledge_base_id == kb_id,
                KnowledgeChunk.deleted == 0,
                KnowledgeChunk.status == "READY",
            )
        )
        result = await db.execute(stmt)
        chunks = list(result.scalars().all())

        # Score chunks
        scored = []
        for chunk in chunks:
            score = self._text_relevance(chunk.content, query)
            if score >= score_threshold:
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored[:top_k]

        items = [
            KnowledgeSearchResultItem(
                chunkId=chunk.id,
                knowledgeBaseId=chunk.knowledge_base_id,
                documentId=chunk.document_id,
                title=chunk.title,
                content=chunk.content,
                score=round(score, 4),
            )
            for chunk, score in top_chunks
        ]

        context = "\n\n".join(item.content for item in items)
        citations = list(set(item.documentId for item in items if item.documentId))

        return KnowledgeSearchResult(
            chunks=items,
            citations=citations,
            context=context,
        )

    async def retrieve_runtime(self, db: AsyncSession, kb_id_str: str, query: str, top_k: int = 5, score_threshold: float = 0.5) -> KnowledgeSearchResult | None:
        """Runtime retrieval used by node executors. kb_id_str may be a string ID."""
        try:
            kb_id = int(kb_id_str)
        except (ValueError, TypeError):
            return None
        result = await self.search(db, kb_id, query, top_k, score_threshold)
        return result

    # ---------- Serialization ----------

    @staticmethod
    def _kb_to_dict(kb: KnowledgeBase) -> dict:
        return {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "configId": kb.config_id,
            "embeddingModel": kb.embedding_model,
            "chunkSize": kb.chunk_size,
            "chunkOverlap": kb.chunk_overlap,
            "status": kb.status,
            "documentCount": kb.document_count,
            "chunkCount": kb.chunk_count,
            "charCount": kb.char_count,
            "createdAt": kb.created_at.isoformat() if kb.created_at else None,
            "updatedAt": kb.updated_at.isoformat() if kb.updated_at else None,
        }

    @staticmethod
    def _doc_to_dict(doc: KnowledgeDocument) -> dict:
        return {
            "id": doc.id,
            "knowledgeBaseId": doc.knowledge_base_id,
            "title": doc.title,
            "sourceType": doc.source_type,
            "sourceUrl": doc.source_url,
            "fileName": doc.file_name,
            "tags": doc.tags,
            "status": doc.status,
            "charCount": doc.char_count,
            "errorMessage": doc.error_message,
            "createdAt": doc.created_at.isoformat() if doc.created_at else None,
            "updatedAt": doc.updated_at.isoformat() if doc.updated_at else None,
        }

    @staticmethod
    def _task_to_dict(task: KnowledgeIndexTask) -> dict:
        return {
            "id": task.id,
            "knowledgeBaseId": task.knowledge_base_id,
            "documentId": task.document_id,
            "status": task.status,
            "progress": task.progress,
            "totalChunks": task.total_chunks,
            "finishedChunks": task.finished_chunks,
            "errorMessage": task.error_message,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }


knowledge_service = KnowledgeService()
