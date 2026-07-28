from __future__ import annotations

from typing import Any, Protocol

from ci_assistant.domain.ci import (
    CIEvent,
    CommitChange,
    JobRun,
    LogArtifact,
    PipelineRun,
    ProviderCapability,
)


class ProviderError(Exception):
    """Stable error boundary around CI-specific failures."""


class AuthenticationError(ProviderError):
    pass


class ResourceNotFoundError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class CIProvider(Protocol):
    provider_type: str
    connection_id: str

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        """返回或维护 ``capabilities`` 对应的能力信息。"""
        ...

    async def test_connection(self) -> dict[str, Any]:
        """检查 ``test_connection`` 对应的服务状态。"""
        ...

    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun:
        """获取 ``get_run`` 对应的数据。"""
        ...

    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]:
        """列出 ``list_jobs`` 对应的数据。"""
        ...

    async def get_job(self, project_ref: str, job_id: str) -> JobRun:
        """获取 ``get_job`` 对应的数据。"""
        ...

    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact:
        """获取 ``get_job_log`` 对应的数据。"""
        ...

    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]:
        """列出 ``list_changes`` 对应的数据。"""
        ...

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None:
        """校验 ``verify_webhook`` 对应的约束。"""
        ...

    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent:
        """解析或加载 ``parse_webhook`` 对应的数据。"""
        ...
