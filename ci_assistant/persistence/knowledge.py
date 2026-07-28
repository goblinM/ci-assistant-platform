from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import IngestionJob, KnowledgeChunk, KnowledgeDocument
from .repositories import Repository


class KnowledgeRepository(Repository[KnowledgeDocument]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeDocument)

    async def find_active_hash(
        self, tenant_id: UUID, content_hash: str
    ) -> KnowledgeDocument | None:
        """执行 ``find_active_hash`` 对应的领域操作。"""
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.content_hash == content_hash,
                KnowledgeDocument.status != "deleted",
            )
        )
        return result.scalars().first()

    async def list_scoped(
        self,
        tenant_id: UUID,
        *,
        project_id: UUID | None = None,
    ) -> Sequence[KnowledgeDocument]:
        """列出 ``list_scoped`` 对应的数据。"""
        statement = select(KnowledgeDocument).where(
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.status != "deleted",
        )
        if project_id is not None:
            statement = statement.where(
                KnowledgeDocument.project_id.in_([None, project_id])
            )
        result = await self.session.execute(
            statement.order_by(KnowledgeDocument.created_at.desc())
        )
        return result.scalars().all()

    async def latest_version(
        self,
        tenant_id: UUID,
        title: str,
        project_id: UUID | None,
    ) -> KnowledgeDocument | None:
        """执行 ``latest_version`` 对应的领域操作。"""
        statement = (
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.title == title,
                KnowledgeDocument.project_id == project_id,
                KnowledgeDocument.status != "deleted",
            )
            .order_by(KnowledgeDocument.version.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def add_chunks(
        self,
        document: KnowledgeDocument,
        chunks: list[str],
    ) -> None:
        """执行 ``add_chunks`` 对应的领域操作。"""
        self.session.add_all(
            [
                KnowledgeChunk(
                    document_id=document.id,
                    tenant_id=document.tenant_id,
                    project_id=document.project_id,
                    provider=document.provider,
                    ordinal=ordinal,
                    content=content,
                    metadata_={
                        "title": document.title,
                        "source_type": document.source_type,
                        "source_url": document.source_url,
                        "license": document.license,
                    },
                    vector_id=None,
                )
                for ordinal, content in enumerate(chunks)
            ]
        )
        await self.session.flush()

    async def create_ingestion_job(
        self, document: KnowledgeDocument, idempotency_key: str
    ) -> IngestionJob:
        """创建 ``create_ingestion_job`` 对应的领域对象或结果。"""
        job = IngestionJob(
            document_id=document.id,
            status="queued",
            idempotency_key=idempotency_key,
            error=None,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def logical_delete(self, document: KnowledgeDocument) -> None:
        """删除 ``logical_delete`` 对应的数据。"""
        document.status = "deleted"
        await self.session.flush()
