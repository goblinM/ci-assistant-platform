import asyncio
from unittest.mock import AsyncMock, MagicMock

from ci_assistant.domain.ci import PipelineRun, ProviderCapability, RunStatus
from ci_assistant.tools import ProviderToolExecutor, default_tool_specs


def test_tool_candidates_obey_provider_capabilities_and_keywords() -> None:
    provider = MagicMock()
    provider.capabilities = frozenset(
        {ProviderCapability.RUN_READ, ProviderCapability.JOB_READ}
    )
    executor = ProviderToolExecutor(default_tool_specs())

    candidates = executor.candidates(provider, text="pipeline failed in runner")

    assert {item.name for item in candidates} == {
        "get_run_context",
        "get_job_context",
    }


def test_tool_execution_receives_provider_not_global_client() -> None:
    provider = MagicMock()
    provider.provider_type = "gitlab"
    provider.capabilities = frozenset(
        {ProviderCapability.RUN_READ, ProviderCapability.JOB_READ}
    )
    provider.get_run = AsyncMock(
        return_value=PipelineRun(
            provider="gitlab",
            connection_id="main",
            project_ref="group/project",
            run_id="42",
            status=RunStatus.FAILED,
        )
    )
    provider.list_jobs = AsyncMock(return_value=[])
    executor = ProviderToolExecutor(default_tool_specs())

    result = asyncio.run(
        executor.execute(
            "get_run_context",
            provider,
            {"project_ref": "group/project", "run_id": "42"},
        )
    )

    assert result["run"]["status"] == "failed"
    provider.get_run.assert_awaited_once_with("group/project", "42")

