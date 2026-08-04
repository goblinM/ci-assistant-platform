from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.persistence.entities import (
    IngestionJob,
    KnowledgeChunk,
    KnowledgeDocument,
)

from .index import FaissIndexStore, IndexedChunk


EmbeddingFunction = Callable[[list[str]], np.ndarray]


class KnowledgeIndexer:
    """为单租户重建版本化 FAISS 索引，并维护文档和入库任务状态。"""

    def __init__(
        self,
        storage_path: Path,
        embed: EmbeddingFunction,
        *,
        dimension: int = 384,
    ) -> None:
        self.storage_path = storage_path
        self.embed = embed
        self.dimension = dimension

    async def rebuild_tenant(self, session: AsyncSession, tenant_id: UUID) -> str:
        """读取租户有效 Chunk、生成向量并原子发布新索引版本；空知识库也发布空版本。"""
        result = await session.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeDocument.status.in_(["uploaded", "indexing", "active"]),
            )
            .order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal)
        )
        rows = result.all()
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        if not rows:
            FaissIndexStore(
                self.storage_path / str(tenant_id),
                dimension=self.dimension,
            ).publish(
                version=version,
                vectors=np.empty((0, self.dimension), dtype="float32"),
                chunks=[],
            )
            return version

        contents = [chunk.content for chunk, _ in rows]
        vectors = np.asarray(self.embed(contents), dtype="float32")
        if vectors.ndim != 2 or vectors.shape[0] != len(rows):
            raise ValueError("embedding function returned an invalid matrix")
        indexed = []
        for (chunk, document), vector in zip(rows, vectors):
            vector_id = chunk.id.int & ((1 << 63) - 1)
            chunk.vector_id = vector_id
            document.status = "active"
            indexed.append(
                IndexedChunk(
                    vector_id=vector_id,
                    content=chunk.content,
                    tenant_id=str(chunk.tenant_id),
                    project_id=str(chunk.project_id) if chunk.project_id else None,
                    provider=chunk.provider,
                    metadata={
                        **chunk.metadata_,
                        "document_id": str(document.id),
                        "chunk_id": str(chunk.id),
                    },
                )
            )
        store = FaissIndexStore(
            self.storage_path / str(tenant_id),
            dimension=vectors.shape[1],
        )
        store.publish(version=version, vectors=vectors, chunks=indexed)
        await session.flush()
        return version

    async def complete_job(
        self,
        session: AsyncSession,
        job_id: UUID,
        *,
        error: str | None = None,
    ) -> None:
        """将入库任务标记为成功或失败，并限制持久化错误信息长度。"""
        job = await session.get(IngestionJob, job_id)
        if job is not None:
            job.status = "failed" if error else "succeeded"
            job.error = error[:1000] if error else None
            await session.flush()
