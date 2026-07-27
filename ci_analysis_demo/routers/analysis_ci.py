import uuid
from collections.abc import Awaitable

from fastapi import APIRouter, Depends, HTTPException

from ..clients.gitlab_client import GitLabClientError
from ..schemas.analysis_schema import AnalysisLogRequest, AnalysisLogResponse, ToolMode
from ..schemas.job_schema import AnalyzeGitlabJobRequest
from ..services.llm_service import analyze_gitlab_job_log, analyze_log_by_mode
from ..utils.custom_exceptions import LLMResponseFormatError, LLMServiceError, LLMTimeoutError
from ..utils.dependencies import get_gitlab_client, get_retriever, get_tools_executor

router = APIRouter(prefix="/ci", tags=["ci"])


async def _execute_analysis(
        operation: Awaitable[AnalysisLogResponse],
) -> AnalysisLogResponse:
    """统一转换分析服务和 GitLab 客户端异常。"""
    try:
        return await operation
    except LLMTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Upstream LLM timeout") from exc
    except LLMResponseFormatError as exc:
        raise HTTPException(status_code=502, detail="Invalid LLM response format") from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=502, detail="LLM service unavailable") from exc
    except GitLabClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitLab service unavailable: {exc}",
        ) from exc


async def _analyze_request(
        data: AnalysisLogRequest,
        retriever,
        tools_executor,
) -> AnalysisLogResponse:
    trace_id = data.request_id or uuid.uuid4().hex
    return await _execute_analysis(analyze_log_by_mode(
        log_text=data.log_text,
        retriever=retriever,
        tools_executor=tools_executor,
        project_name=data.project_name,
        pipeline_id=data.pipeline_id,
        job_name=data.job_name,
        use_rag=data.use_rag,
        use_tools=data.use_tools,
        tool_mode=data.tool_mode,
        trace_id=trace_id,
    ))


@router.post("/analyze-log", response_model=AnalysisLogResponse)
async def analysis_ci_log(
        data: AnalysisLogRequest,
        retriever=Depends(get_retriever),
        tools_executor=Depends(get_tools_executor),
):
    """统一日志分析入口，通过 use_rag、use_tools 和 tool_mode 选择分析链路。"""
    return await _analyze_request(data, retriever, tools_executor)


@router.post(
    "/analyze-rag-log",
    response_model=AnalysisLogResponse,
    deprecated=True,
)
async def analysis_ci_log_rag(
        data: AnalysisLogRequest,
        retriever=Depends(get_retriever),
        tools_executor=Depends(get_tools_executor),
):
    """兼容旧 RAG 接口，新调用请使用 /analyze-log。"""
    rag_request = data.model_copy(update={
        "use_rag": True,
        "use_tools": False,
        "tool_mode": ToolMode.none,
    })
    return await _analyze_request(rag_request, retriever, tools_executor)


@router.post(
    "/analyze-tool-rag-log",
    response_model=AnalysisLogResponse,
    deprecated=True,
)
async def analysis_ci_log_rag_tool(
        data: AnalysisLogRequest,
        retriever=Depends(get_retriever),
        tools_executor=Depends(get_tools_executor),
):
    """兼容旧规则 Tool 接口，新调用请使用 /analyze-log。"""
    rule_request = data.model_copy(update={
        "use_rag": True,
        "use_tools": True,
        "tool_mode": ToolMode.rule,
    })
    return await _analyze_request(rule_request, retriever, tools_executor)


@router.post(
    "/analyze-autonomous-tool-log",
    response_model=AnalysisLogResponse,
    deprecated=True,
)
async def analysis_ci_log_autonomous_tool(
        data: AnalysisLogRequest,
        retriever=Depends(get_retriever),
        tools_executor=Depends(get_tools_executor),
):
    """兼容旧自主 Tool 接口，新调用请使用 /analyze-log。"""
    autonomous_request = data.model_copy(update={
        "use_rag": True,
        "use_tools": True,
        "tool_mode": ToolMode.llm,
    })
    return await _analyze_request(autonomous_request, retriever, tools_executor)


@router.post("/analyze-gitlab-job", response_model=AnalysisLogResponse)
async def analyze_gitlab_job(
        data: AnalyzeGitlabJobRequest,
        retriever=Depends(get_retriever),
        gitlab_client=Depends(get_gitlab_client),
        tools_executor=Depends(get_tools_executor),
):
    """从 GitLab 获取 Job 和 Trace，再复用统一日志分析链路。"""
    trace_id = data.request_id or uuid.uuid4().hex
    return await _execute_analysis(analyze_gitlab_job_log(
        data=data,
        retriever=retriever,
        gitlab_client=gitlab_client,
        trace_id=trace_id,
        tools_executor=tools_executor,
    ))
