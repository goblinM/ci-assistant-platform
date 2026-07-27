from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from ci_assistant.core.config import load_settings
from ci_assistant.knowledge.embeddings import HashingEmbedder
from ci_assistant.knowledge.indexing import KnowledgeIndexer
from ci_assistant.persistence.database import Database
from ci_assistant.persistence.entities import IngestionJob
from ci_assistant.schemas.knowledge import CreateKnowledgeDocument
from ci_assistant.services.knowledge import KnowledgeService


def _document_content(item: dict[str, Any]) -> str:
    fields = {
        key: item.get(key)
        for key in (
            "doc_id",
            "title",
            "source_name",
            "ecosystem",
            "language",
            "package_manager",
            "build_tool",
            "category",
            "stage",
            "error_type",
            "severity",
            "keywords",
            "symptom",
            "root_causes",
            "diagnosis_steps",
            "suggestions",
            "content",
            "embedding_text",
        )
    }
    return json.dumps(fields, ensure_ascii=False)


async def import_dataset(path: Path, tenant_id: UUID) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("knowledge dataset root must be a JSON array")
    settings = load_settings()
    database = Database.from_config(settings.database)
    created = 0
    duplicates = 0
    try:
        async with database.session() as session:
            service = KnowledgeService()
            for item in raw:
                if not isinstance(item, dict) or not item.get("doc_id") or not item.get("title"):
                    raise ValueError("every knowledge item requires doc_id and title")
                result = await service.create(
                    session,
                    CreateKnowledgeDocument(
                        tenant_id=tenant_id,
                        title=f"[{item['doc_id']}] {item['title']}",
                        format="json",
                        content=_document_content(item),
                        source_type=str(item.get("source_type") or "dataset"),
                        source_url=item.get("source_url"),
                        license="Not specified by dataset",
                    ),
                )
                if result.duplicate:
                    duplicates += 1
                else:
                    created += 1

            embedder = HashingEmbedder(settings.knowledge.embedding_dimension)
            indexer = KnowledgeIndexer(
                settings.knowledge.storage_path,
                lambda texts: embedder.encode(texts, normalize_embeddings=True),
                dimension=settings.knowledge.embedding_dimension,
            )
            index_version = await indexer.rebuild_tenant(session, tenant_id)
            jobs = (
                await session.execute(
                    select(IngestionJob).where(IngestionJob.status == "queued")
                )
            ).scalars()
            completed_jobs = 0
            for job in jobs:
                job.status = "succeeded"
                completed_jobs += 1
            return {
                "input_documents": len(raw),
                "created": created,
                "duplicates": duplicates,
                "completed_jobs": completed_jobs,
                "index_version": index_version,
            }
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-import a structured JSON knowledge dataset and publish one index."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(import_dataset(args.path, args.tenant_id)),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
