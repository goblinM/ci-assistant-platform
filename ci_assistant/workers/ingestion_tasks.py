from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from ci_assistant.core.config import load_settings
from ci_assistant.core.errors import ErrorCode
from ci_assistant.knowledge.indexing import KnowledgeIndexer
from ci_assistant.persistence.database import Database
from ci_assistant.persistence.entities import IngestionJob, KnowledgeDocument

from .celery_app import app
from .task_logging import log_task_failure


logger = logging.getLogger(__name__)

if app is None:
    raise RuntimeError("Celery must be installed to load worker tasks")


@app.task(
    bind=True,
    name="ci_assistant.ingest_document",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def ingest_document(self, document_id: str) -> dict[str, Any]:
    """索引单篇知识文档，并以安全字段记录失败事件。"""

    try:
        return asyncio.run(_index_document(document_id))
    except Exception as exc:
        log_task_failure(
            logger,
            task_name="ci_assistant.ingest_document",
            identifier=document_id,
            error_code=ErrorCode.KNOWLEDGE_INGESTION_FAILED.value,
            exception=exc,
        )
        raise


async def _index_document(document_id: str) -> dict[str, Any]:
    from ci_assistant.knowledge.embeddings import HashingEmbedder

    settings = load_settings()
    database = Database.from_config(settings.database)
    try:
        async with database.session() as session:
            document = await session.get(KnowledgeDocument, UUID(document_id))
            if document is None:
                return {"document_id": document_id, "status": "not_found"}
            if document.status != "deleted":
                document.status = "indexing"
            model = HashingEmbedder(settings.knowledge.embedding_dimension)
            indexer = KnowledgeIndexer(
                settings.knowledge.storage_path,
                lambda texts: model.encode(texts, normalize_embeddings=True),
                dimension=model.get_sentence_embedding_dimension(),
            )
            version = await indexer.rebuild_tenant(session, document.tenant_id)
            jobs = (
                await session.execute(
                    select(IngestionJob).where(
                        IngestionJob.document_id == document.id,
                        IngestionJob.status == "queued",
                    )
                )
            ).scalars().all()
            for job in jobs:
                job.status = "succeeded"
            return {
                "document_id": document_id,
                "status": "succeeded",
                "index_version": version,
            }
    finally:
        await database.dispose()


@app.task(
    bind=True,
    name="ci_assistant.reindex_knowledge",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def reindex_knowledge(self, tenant_id: str) -> dict[str, Any]:
    """重建租户知识索引，并以安全字段记录失败事件。"""

    try:
        return asyncio.run(_reindex_tenant(tenant_id))
    except Exception as exc:
        log_task_failure(
            logger,
            task_name="ci_assistant.reindex_knowledge",
            identifier=tenant_id,
            error_code=ErrorCode.KNOWLEDGE_INGESTION_FAILED.value,
            exception=exc,
        )
        raise


async def _reindex_tenant(tenant_id: str) -> dict[str, Any]:
    from ci_assistant.knowledge.embeddings import HashingEmbedder

    settings = load_settings()
    database = Database.from_config(settings.database)
    try:
        async with database.session() as session:
            model = HashingEmbedder(settings.knowledge.embedding_dimension)
            indexer = KnowledgeIndexer(
                settings.knowledge.storage_path,
                lambda texts: model.encode(texts, normalize_embeddings=True),
                dimension=model.get_sentence_embedding_dimension(),
            )
            version = await indexer.rebuild_tenant(session, UUID(tenant_id))
            return {
                "tenant_id": tenant_id,
                "status": "succeeded",
                "index_version": version,
            }
    finally:
        await database.dispose()
