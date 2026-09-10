from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from ci_assistant.core.config import load_settings
from ci_assistant.core.errors import ErrorCode
from ci_assistant.core.metrics import (
    AGENT_INPUT_TOKENS,
    AGENT_ROUNDS,
    AGENT_RUNS,
    AGENT_TOOL_CALLS,
    observe_agent_steps,
    DIAGNOSIS_TASKS,
)
from ci_assistant.diagnosis.agent_runtime import AgentRuntimeLimits, resolve_diagnosis_mode
from ci_assistant.diagnosis.orchestrator import DiagnosisOrchestrator
from ci_assistant.domain.ci import RunStatus
from ci_assistant.knowledge.embeddings import build_embedder
from ci_assistant.knowledge.index import FaissIndexStore
from ci_assistant.knowledge.retrieval import HybridRetriever
from ci_assistant.knowledge.reranking import build_reranker, rerank_with_fallback
from ci_assistant.llm.gateway import OpenAIDiagnosisGateway, RuleBasedDiagnosisGateway
from ci_assistant.persistence.database import Database
from ci_assistant.persistence.agent import AgentRunRepository
from ci_assistant.persistence.diagnoses import DiagnosisRepository
from ci_assistant.persistence.entities import AgentRun, Diagnosis
from ci_assistant.providers.manager import build_provider_manager
from ci_assistant.schemas.result import DiagnosisResult, Reference
from ci_assistant.schemas.agent import AgentRunState
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
    """运行 Celery 诊断任务，并把异步实现桥接到当前 Worker 进程。

    任务仅接收诊断记录 ID，业务输入由异步处理函数从数据库读取。连接或超时异常由 Celery
    按指数退避策略最多重试三次；所有未处理异常先记录不含日志正文的稳定错误字段，再重新
    抛出给 Celery 更新任务状态。
    """

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
    """完成单条诊断记录从 ``queued`` 到终态的异步处理。

    查询记录并使已成功任务幂等返回，然后标记为运行中；按上下文选择 Provider、失败 Job
    和日志，在租户 ACL 内检索知识并执行可降级精排，再调用诊断编排器。成功时持久化结果
    与追踪，异常时标记失败并抛出，最后释放数据库连接池。
    """

    settings = load_settings()
    database = Database.from_config(settings.database)
    try:
        async with database.session() as session:
            # 数据库中获取对应的任务
            repository = DiagnosisRepository(session)
            identifier = UUID(diagnosis_id)
            diagnosis = await repository.get_for_processing(identifier)
            if diagnosis is None:
                existing = await repository.get(identifier)
                status = "already_processing" if existing is not None else "not_found"
                DIAGNOSIS_TASKS.labels(status=status).inc()
                return {"diagnosis_id": diagnosis_id, "status": status}
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
                if (
                    job_id
                    and project_ref
                    and context.get("diagnostic_reason") != "runner_unavailable"
                ):
                    fetched_log = (
                        await provider.get_job_log(project_ref, job_id)
                    ).content
                    if fetched_log:
                        log = fetched_log
            # 根绝provider 决定是用 确定性规则诊断 还是 Agent Reasoning-Action-Observation-AppendResult
            gateway = (
                RuleBasedDiagnosisGateway()
                if settings.ai.provider == "rule"
                else OpenAIDiagnosisGateway(settings.ai)
            )
            tenant_id = str(diagnosis.tenant_id)
            project_id = str(diagnosis.project_id) if diagnosis.project_id else None
            provider_type = provider.provider_type if provider else context.get("provider")
            # 构建默认 Hashing Embedder，并按配置启用持久化缓存
            embedder = build_embedder(settings.knowledge)
            # 管理版本化 FAISS 索引，并通过 CURRENT 指针完成原子切换。
            store = FaissIndexStore(
                settings.knowledge.storage_path / tenant_id,
                settings.knowledge.embedding_dimension,
            )
            # 混合检索：租户 ACL 过滤后的向量候选上融合语义、关键词和元数据
            hybrid = HybridRetriever(store)
            # reranker
            reranker = build_reranker(settings.knowledge.reranker)

            async def retrieve(query: str) -> list[Reference]:
                """在租户 ACL 内执行 Hybrid 检索和可降级精排，并转换为真实引用。"""
                vector = embedder.encode([query])[0]
                final_top_k = 5
                candidates = hybrid.retrieve(
                    query_vector=vector,
                    query_text=query,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    provider=provider_type,
                    top_k=(
                        final_top_k
                        * settings.knowledge.reranker.candidate_multiplier
                        if reranker is not None
                        else final_top_k
                    ),
                )
                # 异常时安全降级
                matches = await rerank_with_fallback(
                    reranker,
                    query,
                    candidates,
                    top_k=final_top_k,
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
            # 诊断编排
            orchestrator = DiagnosisOrchestrator(
                gateway,
                tool_executor=ProviderToolExecutor(default_tool_specs()),
                retriever=retrieve,
            )
            # 决定是走workflow还是agent
            effective_mode = resolve_diagnosis_mode(
                str(context.get("mode", "workflow")),
                agent_enabled=settings.agent.enabled,
            )
            agent_run_id = None
            agent_initial_state = None
            agent_resume_observations = None
            agent_recovered_result = None
            agent_checkpoint_writer = None
            if effective_mode == "agent":
                async with database.session() as checkpoint_session:
                    run_repository = AgentRunRepository(checkpoint_session)
                    agent_run = await run_repository.get_or_create(
                        diagnosis.id,
                        diagnosis.tenant_id,
                        "Diagnose the CI failure using trusted read-only evidence",
                    )
                    agent_run_id = agent_run.id
                    (
                        agent_initial_state,
                        agent_resume_observations,
                        recovered_result_snapshot,
                    ) = (
                        await run_repository.load_state(agent_run)
                    )
                    if recovered_result_snapshot is not None:
                        agent_recovered_result = DiagnosisResult.model_validate(
                            recovered_result_snapshot
                        )

                async def persist_checkpoint(checkpoint):
                    """在独立短事务中提交步骤，使 Worker 异常后可从边界续跑。"""
                    async with database.session() as checkpoint_session:
                        run_repository = AgentRunRepository(checkpoint_session)
                        persisted_run = await run_repository.get(agent_run_id)
                        if persisted_run is None:
                            raise RuntimeError("agent run disappeared during checkpoint")
                        await run_repository.checkpoint(persisted_run, checkpoint)

                agent_checkpoint_writer = persist_checkpoint
            output = await orchestrator.diagnose(
                log,
                provider=provider,
                project_ref=project_ref,
                run_id=run_id,
                job_id=job_id,
                use_rag=bool(context.get("use_rag", True)),
                use_tools=bool(context.get("use_tools", True)),
                mode=effective_mode,
                agent_limits=AgentRuntimeLimits(
                    max_rounds=settings.agent.max_rounds,
                    max_tool_calls=settings.agent.max_tool_calls,
                    tool_timeout_seconds=settings.agent.tool_timeout_seconds,
                    context_max_chars=settings.agent.context_max_chars,
                    total_prompt_max_chars=settings.agent.total_prompt_max_chars,
                    max_estimated_input_tokens=(
                        settings.agent.max_estimated_input_tokens
                    ),
                    observation_max_chars=settings.agent.observation_max_chars,
                ),
                agent_timeout_seconds=settings.agent.timeout_seconds,
                agent_initial_state=agent_initial_state,
                agent_resume_observations=agent_resume_observations,
                agent_checkpoint_writer=agent_checkpoint_writer,
                agent_recovered_result=agent_recovered_result,
            )
            if effective_mode == "agent":
                agent_trace = output.trace.get("agent") or {}
                final_state = AgentRunState.model_validate(agent_trace)
                async with database.session() as checkpoint_session:
                    run_repository = AgentRunRepository(checkpoint_session)
                    persisted_run = await run_repository.get(agent_run_id)
                    if persisted_run is not None:
                        await run_repository.finish(persisted_run, final_state)
                AGENT_RUNS.labels(
                    stop_reason=str(agent_trace.get("stop_reason") or "unknown")
                ).inc()
                AGENT_ROUNDS.observe(float(agent_trace.get("rounds") or 0))
                AGENT_TOOL_CALLS.observe(float(agent_trace.get("tool_calls") or 0))
                AGENT_INPUT_TOKENS.observe(
                    float(agent_trace.get("estimated_input_tokens") or 0)
                )
                observe_agent_steps(final_state.steps)
            await repository.mark_succeeded(
                diagnosis,
                result=output.result.model_dump(mode="json"),
                trace=output.trace,
                prompt_version=(
                    "platform-agent-p0-v1"
                    if effective_mode == "agent"
                    else "platform-v1"
                ),
                model_name=settings.ai.model,
            )
            if agent_run_id is not None:
                committed_run = await session.get(AgentRun, agent_run_id)
                if committed_run is not None:
                    committed_run.phase = "diagnosis_committed"
                    await session.flush()
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
