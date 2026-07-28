from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from ci_assistant.core.config import load_settings
from ci_assistant.core.errors import ErrorCode
from ci_assistant.core.metrics import DIAGNOSIS_TASKS
from ci_assistant.diagnosis.orchestrator import DiagnosisOrchestrator
from ci_assistant.domain.ci import RunStatus
from ci_assistant.knowledge.embeddings import HashingEmbedder
from ci_assistant.knowledge.index import FaissIndexStore
from ci_assistant.knowledge.retrieval import HybridRetriever
from ci_assistant.llm.gateway import OpenAIDiagnosisGateway, RuleBasedDiagnosisGateway
from ci_assistant.persistence.database import Database
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import Diagnosis
from ci_assistant.providers.manager import build_provider_manager
from ci_assistant.schemas.result import Reference
from ci_assistant.tools import ProviderToolExecutor, default_tool_specs

from .celery_app import app
from .task_logging import log_task_failure


logger = logging.getLogger(__name__)

if app is None:
    raise RuntimeError("Celery must be installed to load worker tasks")


@app.task(
    bind=True,
    name="ci_assistant.diagnose",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def diagnose(self, diagnosis_id: str) -> dict[str, Any]:
    """执行单条诊断任务，并以安全字段记录失败事件。"""

    try:
        return asyncio.run(_diagnose(diagnosis_id))
    except Exception as exc:
        log_task_failure(
            logger,
            task_name="ci_assistant.diagnose",
            identifier=diagnosis_id,
            error_code=ErrorCode.DIAGNOSIS_FAILED.value,
            exception=exc,
        )
        raise


async def _diagnose(diagnosis_id: str) -> dict[str, Any]:
    settings = load_settings()
    database = Database.from_config(settings.database)
    try:
        async with database.session() as session:
            repository = DiagnosisRepository(session)
            diagnosis = await repository.get(UUID(diagnosis_id))
            if diagnosis is None:
                DIAGNOSIS_TASKS.labels(status="not_found").inc()
                return {"diagnosis_id": diagnosis_id, "status": "not_found"}
            if diagnosis.status == "succeeded":
                return {"diagnosis_id": diagnosis_id, "status": "succeeded"}
            await repository.mark_running(diagnosis)
            context = diagnosis.result or {}
            provider = None
            log = context.get("log", "")
            project_ref = context.get("project_ref")
            run_id = context.get("run_id") or (context.get("run") or {}).get("run_id")
            job_id = context.get("job_id")
            connection_id = context.get("connection_id")
            if connection_id:
                provider = build_provider_manager(settings).get(connection_id)
                if not job_id and project_ref and run_id:
                    jobs = await provider.list_jobs(project_ref, run_id)
                    failed = next(
                        (item for item in jobs if item.status == RunStatus.FAILED),
                        jobs[0] if jobs else None,
                    )
                    job_id = failed.job_id if failed else None
                if job_id and project_ref:
                    log = (await provider.get_job_log(project_ref, job_id)).content

            gateway = (
                RuleBasedDiagnosisGateway()
                if settings.ai.provider == "rule"
                else OpenAIDiagnosisGateway(settings.ai)
            )
            tenant_id = str(diagnosis.tenant_id)
            project_id = str(diagnosis.project_id) if diagnosis.project_id else None
            provider_type = provider.provider_type if provider else context.get("provider")
            embedder = HashingEmbedder(settings.knowledge.embedding_dimension)
            store = FaissIndexStore(
                settings.knowledge.storage_path / tenant_id,
                settings.knowledge.embedding_dimension,
            )
            hybrid = HybridRetriever(store)

            async def retrieve(query: str) -> list[Reference]:
                """按查询条件检索知识数据。"""
                vector = embedder.encode([query])[0]
                matches = hybrid.retrieve(
                    query_vector=vector,
                    query_text=query,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    provider=provider_type,
                )
                return [
                    Reference(
                        id=str(item.get("metadata", {}).get("chunk_id", item["vector_id"])),
                        title=str(item.get("metadata", {}).get("title", "Knowledge")),
                        source=str(
                            item.get("metadata", {}).get(
                                "source_url",
                                item.get("metadata", {}).get("source_type", "knowledge"),
                            )
                        ),
                        content=item["content"],
                        score=item["score"],
                    )
                    for item in matches
                ]

            orchestrator = DiagnosisOrchestrator(
                gateway,
                tool_executor=ProviderToolExecutor(default_tool_specs()),
                retriever=retrieve,
            )
            output = await orchestrator.diagnose(
                log,
                provider=provider,
                project_ref=project_ref,
                run_id=run_id,
                job_id=job_id,
                use_rag=bool(context.get("use_rag", True)),
                use_tools=bool(context.get("use_tools", True)),
            )
            await repository.mark_succeeded(
                diagnosis,
                result=output.result.model_dump(mode="json"),
                trace=output.trace,
                prompt_version="platform-v1",
                model_name=settings.ai.model,
            )
            DIAGNOSIS_TASKS.labels(status="succeeded").inc()
            return {"diagnosis_id": diagnosis_id, "status": "succeeded"}
    except Exception:
        async with database.session() as session:
            diagnosis = await session.get(Diagnosis, UUID(diagnosis_id))
            if diagnosis is not None:
                await DiagnosisRepository(session).mark_failed(
                    diagnosis, "DIAGNOSIS_FAILED"
                )
        DIAGNOSIS_TASKS.labels(status="failed").inc()
        raise
    finally:
        await database.dispose()
