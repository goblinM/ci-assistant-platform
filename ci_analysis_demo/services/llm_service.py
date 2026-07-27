"""
LLM 接入服务。

负责 prompt 构造、上游模型调用、结构化响应校验和重试。
"""
import asyncio
import json
import logging
import re
import time
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from .log_query_service import build_rag_filters, extract_query_from_log
from .tool_calling_service import parse_llm_tool_calls, execute_llm_tool_calls
from ..core.config import get_settings
from ..prompts.build_prompt_templates import build_rag_prompt, build_basic_prompt, build_rag_tool_prompt, \
    build_tool_selection_prompt, build_final_diagnosis_prompt
from ..schemas.analysis_schema import AnalysisLogResponse, ToolMode
from ..schemas.job_schema import AnalyzeGitlabJobRequest, GitLabJobContext
from ..schemas.rag_schema import RAGResult
from ..schemas.trace_schema import AnalysisTrace
from ..tools.base import LLMToolCall, ToolResult, ToolRuntimeContext
from ..tools.rules import extract_primary_error_keyword
from ..services.tool_context_service import collect_tool_context
from ..utils.basic_utils import extract_relevant_lines, mask_sensitive_info, build_enriched_log, _normalize_llm_output
from ..utils.custom_exceptions import LLMResponseFormatError, LLMServiceError, LLMTimeoutError
from ..utils.fallback_func import fallback_rule_analysis
from ..utils.timer import timer

try:
    from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError
except ModuleNotFoundError:
    AsyncOpenAI = None
    OPENAI_TIMEOUT_ERRORS = ()
    OPENAI_SERVICE_ERRORS = ()
else:
    OPENAI_TIMEOUT_ERRORS = (APITimeoutError,)
    OPENAI_SERVICE_ERRORS = (APIConnectionError, APIStatusError, OpenAIError)

logger = logging.getLogger(__name__)
load_dotenv()


async def analyze_log_with_llm(log_text: str) -> AnalysisLogResponse:
    """基础LLM日志分析"""
    prompt = build_basic_prompt(log_text=log_text)
    return await _call_with_retry(prompt)


async def analyze_log_by_mode(
        log_text: str,
        retriever: Any,
        tools_executor: Any,
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        use_rag: bool = True,
        use_tools: bool = True,
        tool_mode: ToolMode = ToolMode.rule,
        trace_id: str | None = None,
        runtime_context: ToolRuntimeContext | None = None,
) -> AnalysisLogResponse:
    """根据请求参数选择统一的日志分析链路。"""
    tools_enabled = use_tools and tool_mode != ToolMode.none

    if tools_enabled and tool_mode == ToolMode.llm:
        # LLM + 自主tool calling
        result = await analyze_log_with_autonomous_tools(
            log_text=log_text,
            retriever=retriever,
            tools_executor=tools_executor,
            project_name=project_name,
            pipeline_id=pipeline_id,
            job_name=job_name,
            use_rag=use_rag,
            trace_id=trace_id,
            runtime_context=runtime_context,
        )
        analysis_mode = "autonomous_tools"
    elif tools_enabled:
        # 规则Tool calling
        result = await analyze_log_with_rag_tool(
            log_text=log_text,
            retriever=retriever,
            tools_executor=tools_executor,
            project_name=project_name,
            pipeline_id=pipeline_id,
            job_name=job_name,
            use_rag=use_rag,
            use_tools=True,
            trace_id=trace_id,
            runtime_context=runtime_context,
        )
        analysis_mode = "rule_tools"
    elif use_rag:
        # 使用RAG
        result = await analyze_log_with_rag(
            log_text=log_text,
            retriever=retriever,
            trace_id=trace_id,
            project_name=project_name,
            runtime_context=runtime_context,
        )
        analysis_mode = "rag"
    else:
        # 单纯LLM
        result = await analyze_log_with_llm(log_text)
        result.trace_id = trace_id
        analysis_mode = "llm"

    result.extra = {
        **(result.extra or {}),
        **(runtime_context.metadata if runtime_context else {}),
        "analysis_mode": analysis_mode,
    }
    return result


async def analyze_log_with_rag(
        log_text: str,
        retriever: Any,
        trace_id: str | None = None,
        project_name: str | None = None,
        runtime_context: ToolRuntimeContext | None = None,
) -> AnalysisLogResponse:
    """LLM+RAG日志分析"""
    settings = get_settings()
    start = time.perf_counter()
    trace = AnalysisTrace(
        trace_id=trace_id or "",
        project_name=project_name,
        log_length=len(log_text),
        rag_enabled=True,
        llm_model=settings.llm_model,
    )
    _record_runtime_context(trace, runtime_context)
    try:
        primary_error = extract_primary_error_keyword(log_text)
        rag_result = _retrieve_rag(log_text, retriever, settings, primary_error)
        _record_rag_trace(trace, rag_result, settings.rag_context_max_chars)
        prompt = build_rag_prompt(
            log_text,
            rag_result,
            max_context_chars=settings.rag_context_max_chars,
        )
        trace.prompt_length = len(prompt)

        with timer() as t:
            result = await _call_with_retry(
                prompt,
                references_override=rag_result.to_references(),
            )
        trace.llm_duration_ms = t["duration_ms"]
        trace.llm_success = True
        trace.schema_valid = True
        trace.error_type = result.error_type
        trace.confidence = result.confidence
        result.trace_id = trace.trace_id or None
        result.extra = trace.extra
        return result
    except Exception as exc:
        trace.error_message = repr(exc)
        raise
    finally:
        trace.total_duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("analysis_trace=%s", trace.model_dump_json())


async def analyze_log_with_rag_tool(
        log_text: str,
        retriever: Any,
        tools_executor: Any,
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        use_rag: bool = True,
        use_tools: bool = True,
        trace_id: str | None = None,
        runtime_context: ToolRuntimeContext | None = None,
) -> AnalysisLogResponse:
    """LLM + RAG + Tool context 整合日志分析"""
    settings = get_settings()
    # 引入trace_id
    start = time.perf_counter()
    trace = AnalysisTrace(
        trace_id=trace_id,
        project_name=project_name,
        pipeline_id=pipeline_id,
        job_name=job_name,
        log_length=len(log_text),
        rag_enabled=use_rag,
        tools_enabled=use_tools,
    )
    _record_runtime_context(trace, runtime_context)
    try:
        primary_error = extract_primary_error_keyword(log_text)
        rag_result = RAGResult(query="", top_k=settings.retrieve_top_k)
        if use_rag:
            rag_result = _retrieve_rag(log_text, retriever, settings, primary_error)
            _record_rag_trace(trace, rag_result, settings.rag_context_max_chars)
        tool_context = {}
        if use_tools:
            with timer() as t:
                tool_context = await collect_tool_context(
                    log_text=log_text,
                    tools_executor=tools_executor,
                    project_name=project_name,
                    pipeline_id=pipeline_id,
                    job_name=job_name,
                    primary_error=primary_error,
                    runtime_context=runtime_context,
                )

            trace.tool_duration_ms = t["duration_ms"]
            trace.tool_names = tool_context.called_tool_names
            trace.successful_tools = tool_context.successful_tool_names
            trace.failed_tools = tool_context.failed_tool_names
            trace.tool_results = [_trace_tool_result(result) for result in tool_context.results]
            trace.extra["successful_tools"] = trace.successful_tools
            trace.extra["failed_tools"] = trace.failed_tools
            trace.extra["tool_results"] = trace.tool_results
        prompt = build_rag_tool_prompt(
            log_text,
            rag_result,
            tool_context,
            max_context_chars=settings.rag_context_max_chars,
        )
        trace.prompt_length = len(prompt)
        trace.llm_model = settings.llm_model

        with timer() as t:
            try:
                raw_result = await _call_with_retry(
                    prompt,
                    references_override=rag_result.to_references(),
                )
            except Exception:
                trace.fallback_used = True
                # llm 失败降级
                raw_result = fallback_rule_analysis(log_text)

        trace.llm_duration_ms = t["duration_ms"]
        trace.llm_success = True

        # 结果输出
        result = AnalysisLogResponse.model_validate(raw_result)
        result.trace_id = trace.trace_id
        result.fallback_used = trace.fallback_used
        result.extra = trace.extra

        trace.schema_valid = True
        trace.error_type = result.error_type
        trace.confidence = result.confidence

        return result
    except Exception as e:
        trace.error_message = repr(e)
        raise

    finally:
        trace.total_duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("analysis_trace=%s", trace.model_dump_json())


async def _call_with_retry(
        prompt: str,
        references_override: list[dict] | None = None,
) -> AnalysisLogResponse:
    """LLM 重试函数"""
    settings = get_settings()
    retry_count = settings.llm_max_retries
    last_error = None
    retryable_errors = (
        *OPENAI_TIMEOUT_ERRORS,
        *OPENAI_SERVICE_ERRORS,
        json.JSONDecodeError,
        ValidationError,
        LLMResponseFormatError,
    )

    for attempt in range(retry_count + 1):
        try:
            return await _call_llm_once(prompt, references_override=references_override)
        except retryable_errors as e:
            last_error = e
            logger.warning("llm call failed, attempt=%s, error=%s", attempt + 1, repr(e))
            if attempt < retry_count:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            break

    if isinstance(last_error, OPENAI_TIMEOUT_ERRORS):
        raise LLMTimeoutError("LLM request timed out") from last_error
    if isinstance(last_error, (json.JSONDecodeError, ValidationError, LLMResponseFormatError)):
        raise LLMResponseFormatError("LLM returned invalid response") from last_error
    raise LLMServiceError("LLM request failed") from last_error


async def _call_llm_once(
        prompt: str,
        references_override: list[dict] | None = None,
) -> AnalysisLogResponse:
    """基础底层LLM接口调用"""
    if AsyncOpenAI is None:
        raise LLMServiceError("OpenAI SDK is not installed")

    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_url,
        timeout=settings.llm_timeout_seconds,
    )
    logger.info("calling llm api, prompt_length=%s", len(prompt))

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "你是一个CI失败分析助手。"},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )

    content = response.choices[0].message.content
    if not content:
        raise LLMResponseFormatError("LLM returned empty content")

    parsed = _normalize_llm_output(json.loads(content), references_override=references_override)

    result = AnalysisLogResponse.model_validate(parsed)
    logger.info("llm api success, error_type=%s", result.error_type)
    return result


async def analyze_gitlab_job_log(data: AnalyzeGitlabJobRequest,
                                 retriever,
                                 gitlab_client,
                                 trace_id: str,
                                 tools_executor):
    """接入gitlab job 然后拉取日志，清洗日志，解析日志，传递日志给LLM"""
    job = await gitlab_client.get_job(
        project_id=data.project_id,
        job_id=data.job_id,
    )
    # trace → 提取关键行 → 脱敏 → 送给 LLM
    job_trace = await gitlab_client.get_job_trace(
        project_id=data.project_id,
        job_id=data.job_id,
    )
    trace = extract_relevant_lines(job_trace)
    mask_trace = mask_sensitive_info(trace)

    # 构造合适的context
    context = GitLabJobContext(
        project_id=data.project_id,
        pipeline_id=data.pipeline_id,
        job_id=data.job_id,
        job_name=job.get("name"),
        stage=job.get("stage"),
        status=job.get("status"),
        branch=job.get("ref"),
        commit_sha=job.get("commit", {}).get("id") if job.get("commit") else None,
        failure_reason=job.get("failure_reason"),
        duration=job.get("duration"),
    )

    enriched_log = build_enriched_log(mask_trace, context)
    runtime_context = ToolRuntimeContext(
        trace_id=trace_id,
        prefetched={
            "gitlab_job": {
                ToolRuntimeContext.cache_key(data.project_id, data.job_id): job,
            },
        },
        metadata={
            "gitlab_bootstrap": {
                "job_prefetched": True,
                "trace_prefetched": True,
                "pipeline_prefetched": False,
            },
        },
    )
    logger.info(
        "gitlab_bootstrap trace_id=%s project_id=%s job_id=%s pipeline_prefetched=false",
        trace_id,
        data.project_id,
        data.job_id,
    )

    return await analyze_log_by_mode(
        log_text=enriched_log,
        retriever=retriever,
        tools_executor=tools_executor,
        project_name=data.project_id,
        pipeline_id=data.pipeline_id,
        job_name=context.job_name,
        use_rag=data.use_rag,
        use_tools=data.use_tools,
        tool_mode=data.tool_mode,
        runtime_context=runtime_context,
        trace_id=trace_id
    )


async def analyze_log_with_autonomous_tools(
        log_text: str,
        retriever,
        tools_executor,
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        use_rag: bool = True,
        trace_id: str | None = None,
        runtime_context: ToolRuntimeContext | None = None,
) -> AnalysisLogResponse:
    settings = get_settings()
    start = time.perf_counter()
    trace = AnalysisTrace(
        trace_id=trace_id,
        project_name=project_name,
        pipeline_id=pipeline_id,
        job_name=job_name,
        log_length=len(log_text),
        rag_enabled=use_rag,
        tools_enabled=True,
        llm_model=settings.llm_model,
    )
    _record_runtime_context(trace, runtime_context)
    try:
        # 1. RAG 检索
        primary_error = extract_primary_error_keyword(log_text)
        rag_result = RAGResult(query="", top_k=settings.retrieve_top_k)
        if use_rag:
            rag_result = _retrieve_rag(log_text, retriever, settings, primary_error)
            _record_rag_trace(trace, rag_result, settings.rag_context_max_chars)

        # 2. 构造工具选择 prompt
        tool_select_prompt = build_tool_selection_prompt(
            log_text=log_text,
            retrieved_docs=rag_result,
            project_name=project_name,
            pipeline_id=pipeline_id,
            job_name=job_name,
            max_context_chars=settings.rag_context_max_chars,
        )
        trace.prompt_length = len(tool_select_prompt)

        # 3. 第一轮 LLM 调用：让模型决定工具
        with timer() as t:
            tool_filter = _build_autonomous_tool_filter(
                log_text=log_text,
                project_name=project_name,
                pipeline_id=pipeline_id,
                job_name=job_name,
                primary_error=primary_error,
            )
            available_tools = tools_executor.get_tools_schema(**tool_filter)
            tool_selection_response = await call_llm_for_tool_selection(
                prompt=tool_select_prompt,
                tools_schema=available_tools,
            )
        trace.tool_selection_duration_ms = t["duration_ms"]
        trace.extra["candidate_tools"] = [
            item["function"]["name"] for item in available_tools
        ]
        trace.extra["tool_filter"] = {
            key: value
            for key, value in tool_filter.items()
            if key not in {"text"}
        }

        # 4. 解析 tool calls
        raw_tool_calls = extract_raw_tool_calls(tool_selection_response)
        tool_calls = parse_llm_tool_calls(raw_tool_calls)
        trace.tool_calls = [_trace_tool_call(call) for call in tool_calls]
        trace.tool_names = [call.tool_name for call in tool_calls]

        # 5. 执行工具
        with timer() as t:
            tool_results = await execute_llm_tool_calls(
                tool_calls=tool_calls,
                tools_executor=tools_executor,
                max_tool_calls=3,
                runtime_context=runtime_context,
            )
        trace.tool_duration_ms = t["duration_ms"]
        trace.tool_results = [_trace_tool_result(result) for result in tool_results]
        trace.successful_tools = [result.tool_name for result in tool_results if result.success]
        trace.failed_tools = [result.tool_name for result in tool_results if not result.success]

        # 6. 构造最终诊断 prompt
        final_prompt = build_final_diagnosis_prompt(
            log_text=log_text,
            retrieved_docs=rag_result,
            tool_results=[result.model_dump() for result in tool_results],
            max_context_chars=settings.rag_context_max_chars,
        )
        trace.final_prompt_length = len(final_prompt)

        # 7. 第二轮 LLM 调用：生成最终诊断
        with timer() as t:
            raw_result = await call_llm_for_final_diagnosis(
                final_prompt,
                references_override=rag_result.to_references(),
            )
        trace.llm_duration_ms = t["duration_ms"]
        trace.llm_success = True

        # 8. Pydantic 校验和 trace 回填
        result = raw_result
        result.trace_id = trace.trace_id
        result.extra = {
            **trace.extra,
            "autonomous_tool_calls": trace.tool_calls,
            "autonomous_tool_results": trace.tool_results,
            "successful_tools": trace.successful_tools,
            "failed_tools": trace.failed_tools,
        }

        trace.schema_valid = True
        trace.error_type = result.error_type
        trace.confidence = result.confidence
        return result
    except Exception as e:
        trace.error_message = repr(e)
        raise
    finally:
        trace.total_duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info("analysis_trace=%s", trace.model_dump_json())


def _retrieve_rag(
        log_text: str,
        retriever: Any,
        settings: Any,
        primary_error: dict | None = None,
) -> RAGResult:
    """统一执行 query 清洗、metadata 过滤和向量召回。"""
    query = extract_query_from_log(log_text)
    if hasattr(retriever, "build_rag_query"):
        query = retriever.build_rag_query(query, primary_error)
    filters = build_rag_filters(log_text, primary_error)
    return retriever.retrieve(
        query=query,
        top_k=settings.retrieve_top_k,
        min_score=settings.rag_min_score,
        filters=filters,
        candidate_multiplier=settings.rag_candidate_multiplier,
    )


def _record_runtime_context(
        trace: AnalysisTrace,
        runtime_context: ToolRuntimeContext | None,
) -> None:
    if runtime_context and runtime_context.metadata:
        trace.extra.update(runtime_context.metadata)


def _record_rag_trace(
        trace: AnalysisTrace,
        rag_result: RAGResult,
        context_max_chars: int,
) -> None:
    """记录rag trace"""
    context = rag_result.to_prompt_context(max_chars=context_max_chars)
    trace.rag_query = rag_result.query
    trace.rag_filters = rag_result.filters
    trace.rag_top_k = rag_result.top_k
    trace.rag_candidate_count = rag_result.candidate_count
    trace.rag_hit_doc_ids = rag_result.hit_doc_ids
    trace.rag_hit_titles = rag_result.hit_titles
    trace.rag_scores = rag_result.scores
    trace.rag_duration_ms = rag_result.duration_ms
    trace.rag_context_length = len(context)
    trace.extra["rag"] = {
        "query": rag_result.query,
        "filters": rag_result.filters,
        "top_k": rag_result.top_k,
        "candidate_count": rag_result.candidate_count,
        "hit_doc_ids": rag_result.hit_doc_ids,
        "hit_titles": rag_result.hit_titles,
        "scores": rag_result.scores,
        "sources": [doc.source for doc in rag_result.documents],
        "error_types": [doc.error_type for doc in rag_result.documents],
        "retrieval_sources": [doc.retrieval_sources for doc in rag_result.documents],
        "duration_ms": rag_result.duration_ms,
        "context_length": len(context),
    }


async def call_llm_for_tool_selection(prompt: str, tools_schema: list[dict]) -> dict:
    """
    第一轮：让 LLM 决定是否调用工具。
    返回原始模型响应。
    :param prompt:
    :param tools_schema:
    :return:
    """
    if AsyncOpenAI is None:
        raise LLMServiceError("OpenAI SDK is not installed")

    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_url,
        timeout=settings.llm_timeout_seconds,
    )
    tools = _ensure_openai_tools_schema(tools_schema)
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": "你是一个CI失败分析助手，负责判断是否需要调用工具。"},
            {"role": "user", "content": prompt},
        ],
        tools=tools,
        tool_choice="auto",
        stream=False,
    )
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response


async def call_llm_for_final_diagnosis(
        prompt: str,
        references_override: list[dict] | None = None,
) -> AnalysisLogResponse:
    """
    第二轮：生成最终结构化诊断。
    """
    return await _call_with_retry(prompt, references_override=references_override)


def extract_raw_tool_calls(response: dict) -> list[dict]:
    """提取原始tool calls"""
    try:
        message = response["choices"][0]["message"]
        return message.get("tool_calls", []) or []
    except Exception:
        return []


def _build_autonomous_tool_filter(
        log_text: str,
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        primary_error: dict | None = None,
) -> dict[str, Any]:
    """为 autonomous tool calling 生成动态工具候选过滤条件。"""
    primary_error = primary_error or extract_primary_error_keyword(log_text)
    tags = ["diagnosis"]
    trigger_keywords: list[str] = []

    if project_name:
        tags.extend(["repository", "gitlab"])

    if pipeline_id or job_name:
        tags.extend(["pipeline", "job", "context"])
        trigger_keywords.extend(["pipeline", "job"])

    if primary_error:
        for field in ("keyword", "matched_text", "error_type", "description"):
            value = primary_error.get(field)
            if value:
                trigger_keywords.append(str(value))
        trigger_keywords.extend(str(group) for group in primary_error.get("groups") or [] if group)

        if primary_error.get("error_type") == "dependency_missing":
            tags.append("dependency")

    return {
        "tags": tags,
        "read_only_only": True,
        "text": log_text,
        "trigger_keywords": trigger_keywords,
        "allowed_tags": ["ci"],
        "allowed_providers": ["local"],
        "max_tools": 8,
    }


def _trace_tool_call(call: LLMToolCall) -> dict:
    return {
        "call_id": call.call_id,
        "tool_name": call.tool_name,
        "arguments": call.arguments,
    }


def _trace_tool_result(result: ToolResult) -> dict:
    return {
        "tool_name": result.tool_name,
        "success": result.success,
        "duration_ms": result.duration_ms,
        "error": result.error,
        "data_summary": _summarize_tool_data(result.data),
    }


def _summarize_tool_data(data: dict | None) -> dict:
    if not data:
        return {}

    summary = {
        "available": data.get("available"),
        "matched_count": data.get("matched_count"),
        "reason": data.get("reason"),
        "data_source": data.get("data_source"),
    }

    if "recent_cases" in data:
        summary["recent_case_count"] = len(data.get("recent_cases") or [])
    if "jobs" in data:
        summary["job_count"] = len(data.get("jobs") or [])
    if "commits" in data:
        summary["commit_count"] = len(data.get("commits") or [])
    if "package_found" in data:
        summary["package_found"] = data.get("package_found")
    if "pipeline" in data and data.get("pipeline"):
        summary["pipeline_status"] = data["pipeline"].get("status")
    if "job" in data and data.get("job"):
        summary["job_status"] = data["job"].get("status")

    return {key: value for key, value in summary.items() if value is not None}


def _ensure_openai_tools_schema(tools_schema: list[dict]) -> list[dict]:
    """兼容内部 schema 和 OpenAI-compatible tools schema。"""
    if not tools_schema:
        return []
    if tools_schema[0].get("type") == "function":
        return tools_schema
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in tools_schema
    ]
