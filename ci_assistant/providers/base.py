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
    def capabilities(self) -> frozenset[ProviderCapability]: ...

    async def test_connection(self) -> dict[str, Any]: ...
    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun: ...
    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]: ...
    async def get_job(self, project_ref: str, job_id: str) -> JobRun: ...
    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact: ...
    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]: ...
    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None: ...
    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent: ...

