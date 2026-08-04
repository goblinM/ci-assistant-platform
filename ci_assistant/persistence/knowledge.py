from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import IngestionJob, KnowledgeChunk, KnowledgeDocument
from .repositories import Repository


class KnowledgeRepository(Repository[KnowledgeDocument]):
    """管理租户知识版本、切片、入库任务和逻辑删除。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeDocument)

    async def find_active_hash(
        self, tenant_id: UUID, content_hash: str
    ) -> KnowledgeDocument | None:
        """按租户和内容哈希查找尚未删除的知识版本，用于入库去重。"""
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
        """列出租户全局及指定项目可见的未删除知识文档。"""
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
        """查找同租户、标题和项目作用域下最新的未删除版本。"""
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
        """按原始顺序保存文档切片，并复制检索所需的作用域和来源元数据。"""
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
        """为知识版本创建具有唯一幂等键的异步索引任务。"""
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
        """将知识文档标记为已删除，保留审计和后续索引重建依据。"""
        document.status = "deleted"
        await self.session.flush()
