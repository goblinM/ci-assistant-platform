from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.knowledge.processing import process_document
from ci_assistant.persistence.entities import IngestionJob, KnowledgeDocument
from ci_assistant.persistence.knowledge import KnowledgeRepository
from ci_assistant.schemas.knowledge import CreateKnowledgeDocument


@dataclass(frozen=True)
class CreatedKnowledge:
    document: KnowledgeDocument
    job: IngestionJob | None
    duplicate: bool


class KnowledgeService:
    async def create(
        self,
        session: AsyncSession,
        payload: CreateKnowledgeDocument,
    ) -> CreatedKnowledge:
        """创建 ``create`` 对应的领域对象或结果。"""
        processed = process_document(payload.content, payload.format)
        repository = KnowledgeRepository(session)
        duplicate = await repository.find_active_hash(
            payload.tenant_id, processed.content_hash
        )
        if duplicate is not None:
            return CreatedKnowledge(duplicate, None, True)

        previous = await repository.latest_version(
            payload.tenant_id,
            payload.title,
            payload.project_id,
        )
        version = previous.version + 1 if previous else 1
        if previous is not None:
            previous.status = "superseded"

        document = KnowledgeDocument(
            tenant_id=payload.tenant_id,
            project_id=payload.project_id,
            provider=payload.provider,
            title=payload.title,
            format=payload.format,
            source_type=payload.source_type,
            source_url=payload.source_url,
            license=payload.license,
            content_hash=processed.content_hash,
            version=version,
            status="uploaded",
            content=processed.normalized_content,
        )
        await repository.add(document)
        await repository.add_chunks(document, processed.chunks)
        job = await repository.create_ingestion_job(
            document, f"ingest:{document.id}:{document.version}"
        )
        return CreatedKnowledge(document, job, False)

    async def delete(
        self,
        session: AsyncSession,
        document_id: UUID,
        tenant_id: UUID,
    ) -> KnowledgeDocument | None:
        """删除 ``delete`` 对应的数据。"""
        repository = KnowledgeRepository(session)
        document = await repository.get(document_id)
        if document is None or document.tenant_id != tenant_id:
            return None
        await repository.logical_delete(document)
        return document
