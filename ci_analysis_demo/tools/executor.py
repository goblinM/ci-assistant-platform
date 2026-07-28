"""
工具注册函数，然后统一调用
统一的管理器来注册和调度这些工具
统一注册、执行、异常隔离
工具统一注册
工具统一执行
未知工具不会打崩系统
单个工具异常不会影响其他工具
每个工具有独立耗时
返回结构统一是 ToolResult
"""
import time
import logging
import inspect
from typing import Any, Dict

from ci_analysis_demo.tools.base import ToolResult, ToolRuntimeContext, ToolSpec

logger = logging.getLogger(__name__)


class ToolsExecutor:
    def __init__(self, gitlab_client=None):
        self._tools: Dict[str, ToolSpec] = {}
        self.gitlab_client = gitlab_client

    def register(self, spec: ToolSpec) -> None:
        """注册工具"""
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")

        self._tools[spec.name] = spec

    def get_tools_schema(
            self,
            tags: list[str] | None = None,
            read_only_only: bool = True,
            text: str | None = None,
            trigger_keywords: list[str] | None = None,
            allowed_tags: list[str] | None = None,
            allowed_providers: list[str] | None = None,
            max_tools: int = 8,
    ) -> list[dict[str, Any]]:
        """
        获取工具的schema
        :return:
        """
        schemas = []
        for spec in self._select_tools(
                tags=tags,
                read_only_only=read_only_only,
                text=text,
                trigger_keywords=trigger_keywords,
                allowed_tags=allowed_tags,
                allowed_providers=allowed_providers,
                max_tools=max_tools,
        ):
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters_schema,
                    },
                }
            )

        return schemas

    async def execute(
            self,
            tool_name: str,
            arguments: dict[str, Any] | None = None,
            runtime_context: ToolRuntimeContext | None = None,
    ) -> ToolResult:
        """单个工具执行"""
        arguments = arguments or {}
        start = time.perf_counter()
        spec = self._tools.get(tool_name)

        if not spec:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Unknown tool: {tool_name}",
                duration_ms=duration_ms,
            )

        try:
            raw_data = await self._execute_by_provider(spec, arguments, runtime_context)

            data = raw_data
            if spec.result_trimmer:
                data = spec.result_trimmer(tool_name, raw_data)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            return ToolResult(
                tool_name=tool_name,
                success=True,
                data=data,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception("tool execution failed, tool_name=%s", tool_name)

            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=repr(e),
                duration_ms=duration_ms,
            )

    async def _execute_by_provider(
            self,
            spec: ToolSpec,
            arguments: dict[str, Any],
            runtime_context: ToolRuntimeContext | None = None,
    ) -> dict[str, Any]:
        """根据 provider 分发工具执行；当前只实现本地函数工具。"""
        if spec.provider != "local":
            raise NotImplementedError(f"Unsupported tool provider: {spec.provider}")

        tool_arguments = self._inject_dependencies(spec, arguments, runtime_context)
        raw_data = spec.func(**tool_arguments)
        if inspect.isawaitable(raw_data):
            raw_data = await raw_data
        return raw_data

    async def execute_many(
            self,
            calls: list[dict[str, Any]],
            runtime_context: ToolRuntimeContext | None = None,
    ) -> list[ToolResult]:
        """批量执行"""
        results: list[ToolResult] = []

        for call in calls:
            result = await self.execute(
                tool_name=call["tool_name"],
                arguments=call.get("arguments", {}),
                runtime_context=runtime_context,
            )
            results.append(result)

        return results

    def list_tools(
            self,
            tags: list[str] | None = None,
            read_only_only: bool | None = None,
            text: str | None = None,
            trigger_keywords: list[str] | None = None,
            allowed_tags: list[str] | None = None,
            allowed_providers: list[str] | None = None,
            max_tools: int = 8,
    ) -> list[str]:
        """列出 ``list_tools`` 对应的数据。"""
        return [
            spec.name
            for spec in self._select_tools(
                tags=tags,
                read_only_only=read_only_only,
                text=text,
                trigger_keywords=trigger_keywords,
                allowed_tags=allowed_tags,
                allowed_providers=allowed_providers,
                max_tools=max_tools,
            )
        ]

    def select_tool_names(
            self,
            tags: list[str] | None = None,
            read_only_only: bool | None = True,
            text: str | None = None,
            trigger_keywords: list[str] | None = None,
            allowed_tags: list[str] | None = None,
            allowed_providers: list[str] | None = None,
            max_tools: int = 8,
    ) -> list[str]:
        """根据 tag / trigger_keywords / read_only 动态选择合适工具名。"""
        return [
            spec.name
            for spec in self._select_tools(
                tags=tags,
                read_only_only=read_only_only,
                text=text,
                trigger_keywords=trigger_keywords,
                allowed_tags=allowed_tags,
                allowed_providers=allowed_providers,
                max_tools=max_tools,
            )
        ]

    def _inject_dependencies(
            self,
            spec: ToolSpec,
            arguments: dict[str, Any],
            runtime_context: ToolRuntimeContext | None = None,
    ) -> dict[str, Any]:
        """依赖注入"""
        injected = dict(arguments)
        parameters = inspect.signature(spec.func).parameters
        accepts_kwargs = any(param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values())
        accepts_gitlab_client = "gitlab_client" in parameters or accepts_kwargs
        if self.gitlab_client and accepts_gitlab_client and "gitlab_client" not in injected:
            injected["gitlab_client"] = self.gitlab_client
        accepts_runtime_context = "runtime_context" in parameters or accepts_kwargs
        if runtime_context and accepts_runtime_context and "runtime_context" not in injected:
            injected["runtime_context"] = runtime_context
        return injected

    def _select_tools(
            self,
            tags: list[str] | None = None,
            read_only_only: bool = True,
            text: str | None = None,
            trigger_keywords: list[str] | None = None,
            allowed_tags: list[str] | None = None,
            allowed_providers: list[str] | None = None,
            max_tools: int = 8,
    ) -> list[ToolSpec]:
        """根据 tag 和触发关键词筛选工具。"""
        candidates: list[ToolSpec] = []
        has_filters = bool(tags or text or trigger_keywords)

        for spec in self._tools.values():
            if not spec.enabled:
                continue

            if read_only_only and not spec.read_only:
                continue

            if allowed_providers and spec.provider not in allowed_providers:
                continue

            if allowed_tags and not self._matches_tags(spec, allowed_tags):
                continue

            if spec.always_candidate:
                candidates.append(spec)
                continue

            if not has_filters:
                candidates.append(spec)
                continue

            tag_matched = self._matches_tags(spec, tags)
            keyword_matched = self._matches_trigger_keywords(spec, text, trigger_keywords)

            if not (tag_matched or keyword_matched):
                continue

            candidates.append(spec)

        return candidates[:max_tools]

    @staticmethod
    def _matches_tags(spec: ToolSpec, tags: list[str] | None) -> bool:
        if not tags:
            return False

        spec_tags = set(spec.tags or [])
        return any(tag in spec_tags for tag in tags)

    @staticmethod
    def _matches_trigger_keywords(
            spec: ToolSpec,
            text: str | None,
            trigger_keywords: list[str] | None,
    ) -> bool:
        spec_keywords = [keyword.lower() for keyword in spec.trigger_keywords or [] if keyword]
        if not spec_keywords:
            return False

        if text:
            lower_text = text.lower()
            if any(keyword in lower_text for keyword in spec_keywords):
                return True

        for keyword in trigger_keywords or []:
            lower_keyword = str(keyword).lower()
            if any(
                    spec_keyword == lower_keyword
                    or spec_keyword in lower_keyword
                    or lower_keyword in spec_keyword
                    for spec_keyword in spec_keywords
            ):
                return True

        return False
