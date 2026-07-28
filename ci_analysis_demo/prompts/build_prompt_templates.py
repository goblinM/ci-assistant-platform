"""
构造prompt文件
"""
import json

from ..prompts.analyze_diagnosis_prompt import ANALYZE_DIAGNOSIS_PROMPT
from ..prompts.analyze_log_prompt import ANALYZE_LOG_PROMPT
from ..prompts.analyze_log_rag_prompt import ANALYZE_LOG_RAG_PROMPT
from ..prompts.analyze_log_rag_tool_regular import ANALYZE_LOG_RAG_TOOL_REGULAR_PROMPT
from ..prompts.analyze_tool_select_prompt import ANALYZE_TOOL_SELECT_PROMPT
from ..schemas.rag_schema import RAGResult
from ..tools.base import ToolContext
from ..utils.basic_utils import _format_docs


def build_basic_prompt(log_text: str) -> str:
    """基础LLM日志分析"""
    prompt = ANALYZE_LOG_PROMPT.format(log_text=log_text).strip()
    return prompt


def _build_knowledge_context(
        retrieved_docs: RAGResult | list[dict],
        max_context_chars: int | None = None,
) -> str:
    if isinstance(retrieved_docs, RAGResult):
        return retrieved_docs.to_prompt_context(max_chars=max_context_chars)
    context = _format_docs(retrieved_docs)
    return context[:max_context_chars] if max_context_chars else context


def build_rag_prompt(
        log_text: str,
        retrieved_docs: RAGResult | list[dict],
        max_context_chars: int | None = None,
) -> str:
    """构建rag prompt"""
    context = _build_knowledge_context(retrieved_docs, max_context_chars)
    return ANALYZE_LOG_RAG_PROMPT.format(log_text=log_text, context=context).strip()


def build_rag_tool_prompt(
        log_text: str,
        retrieved_docs: RAGResult | list[dict],
        tool_context: ToolContext | dict,
        max_context_chars: int | None = None,
) -> str:
    """构建rag + tool context prompt"""
    context = _build_knowledge_context(retrieved_docs, max_context_chars)
    # ToolContext要转换成dict
    if isinstance(tool_context, ToolContext):
        tool_context_data = tool_context.to_prompt_context()
    else:
        tool_context_data = tool_context
    tool_context_text = json.dumps(tool_context_data, ensure_ascii=False, indent=2)
    return ANALYZE_LOG_RAG_TOOL_REGULAR_PROMPT.format(
        log_text=log_text,
        knowledge_context=context,
        tool_context_text=tool_context_text,
    ).strip()


def build_tool_selection_prompt(
        log_text: str,
        retrieved_docs: RAGResult | list[dict],
        project_name: str | None = None,
        pipeline_id: str | None = None,
        job_name: str | None = None,
        max_context_chars: int | None = None,
) -> str:
    """
    第一轮 Prompt：工具选择 Prompt
    让模型直接诊断，而是让它判断是否需要工具
    :param log_text:
    :param retrieved_docs:
    :param project_name:
    :param pipeline_id:
    :param job_name:
    :return:
    """
    knowledge_context = _build_knowledge_context(retrieved_docs, max_context_chars)
    return ANALYZE_TOOL_SELECT_PROMPT.format(
        log_text=log_text,
        knowledge_context=knowledge_context,
        project_name=project_name,
        pipeline_id=pipeline_id,
        job_name=job_name
    ).strip()


def build_final_diagnosis_prompt(
    log_text: str,
    retrieved_docs: RAGResult | list[dict],
    tool_results: list[dict],
    max_context_chars: int | None = None,
) -> str:
    """创建 ``build_final_diagnosis_prompt`` 对应的领域对象或结果。"""
    knowledge_context = _build_knowledge_context(retrieved_docs, max_context_chars)

    tool_context = json.dumps(
        tool_results,
        ensure_ascii=False,
        indent=2,
    )
    return ANALYZE_DIAGNOSIS_PROMPT.format(
        knowledge_context=knowledge_context,
        tool_context=tool_context,
        log_text=log_text
    ).strip()
