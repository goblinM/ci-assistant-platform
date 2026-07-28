from __future__ import annotations

import hmac
from typing import Any

from ci_assistant.domain.ci import (
    CIEvent,
    CommitChange,
    JobRun,
    LogArtifact,
    PipelineRun,
    ProviderCapability,
    RunStatus,
)
from ci_assistant.providers.base import AuthenticationError

from .client import GitLabClient


_STATUS_MAP = {
    "created": RunStatus.CREATED,
    "pending": RunStatus.QUEUED,
    "waiting_for_resource": RunStatus.QUEUED,
    "preparing": RunStatus.QUEUED,
    "running": RunStatus.RUNNING,
    "success": RunStatus.SUCCESS,
    "failed": RunStatus.FAILED,
    "canceled": RunStatus.CANCELED,
    "skipped": RunStatus.SKIPPED,
}


def normalize_status(value: str | None) -> RunStatus:
    """将 ``normalize_status`` 对应的数据规范化。"""
    return _STATUS_MAP.get(value or "", RunStatus.UNKNOWN)


class GitLabProvider:
    provider_type = "gitlab"
    capabilities = frozenset(ProviderCapability)

    def __init__(
        self,
        connection_id: str,
        client: GitLabClient,
        *,
        webhook_secret: str | None = None,
        max_log_chars: int = 200_000,
    ) -> None:
        self.connection_id = connection_id
        self.client = client
        self.webhook_secret = webhook_secret
        self.max_log_chars = max_log_chars

    async def test_connection(self) -> dict[str, Any]:
        """检查 ``test_connection`` 对应的服务状态。"""
        return {"ok": True, "provider": "gitlab", "connection_id": self.connection_id}

    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun:
        """获取 ``get_run`` 对应的数据。"""
        payload = await self.client.get_pipeline(project_ref, run_id)
        return PipelineRun(
            provider="gitlab",
            connection_id=self.connection_id,
            project_ref=project_ref,
            run_id=str(payload["id"]),
            status=normalize_status(payload.get("status")),
            branch=payload.get("ref"),
            commit_sha=payload.get("sha"),
            web_url=payload.get("web_url"),
        )

    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]:
        """列出 ``list_jobs`` 对应的数据。"""
        payloads = await self.client.list_pipeline_jobs(project_ref, run_id)
        return [self._map_job(payload, run_id) for payload in payloads]

    async def get_job(self, project_ref: str, job_id: str) -> JobRun:
        """获取 ``get_job`` 对应的数据。"""
        payload = await self.client.get_job(project_ref, job_id)
        pipeline = payload.get("pipeline") or {}
        return self._map_job(payload, str(pipeline.get("id") or ""))

    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact:
        """获取 ``get_job_log`` 对应的数据。"""
        content = await self.client.get_job_trace(project_ref, job_id)
        return LogArtifact(
            job_id=job_id,
            content=content[-self.max_log_chars :],
            truncated=len(content) > self.max_log_chars,
            original_length=len(content),
        )

    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]:
        """列出 ``list_changes`` 对应的数据。"""
        run = await self.get_run(project_ref, run_id)
        payloads = await self.client.list_commits(project_ref, run.branch)
        return [
            CommitChange(
                commit_sha=str(item["id"]),
                title=item.get("title") or "",
                message=item.get("message"),
                author_name=item.get("author_name"),
                web_url=item.get("web_url"),
            )
            for item in payloads
        ]

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None:
        """校验 ``verify_webhook`` 对应的约束。"""
        if self.webhook_secret is None:
            raise AuthenticationError("GitLab webhook secret is not configured")
        supplied = headers.get("X-Gitlab-Token") or headers.get("x-gitlab-token") or ""
        if not hmac.compare_digest(supplied, self.webhook_secret):
            raise AuthenticationError("Invalid GitLab webhook token")

    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent:
        """解析或加载 ``parse_webhook`` 对应的数据。"""
        project = payload.get("project") or {}
        obj = payload.get("object_attributes") or {}
        build_id = payload.get("build_id")
        external_id = str(obj.get("id") or build_id or "")
        return CIEvent(
            provider="gitlab",
            external_event_id=external_id,
            event_type=str(payload.get("object_kind") or "unknown"),
            project_ref=str(project.get("path_with_namespace") or project.get("id") or ""),
            run_id=str(obj.get("id")) if obj.get("id") is not None else None,
            job_id=str(build_id) if build_id is not None else None,
            status=normalize_status(obj.get("status") or payload.get("build_status")),
        )

    @staticmethod
    def _map_job(payload: dict[str, Any], run_id: str) -> JobRun:
        runner = payload.get("runner") or {}
        return JobRun(
            job_id=str(payload["id"]),
            run_id=run_id,
            name=payload.get("name") or "",
            stage=payload.get("stage"),
            status=normalize_status(payload.get("status")),
            failure_reason=payload.get("failure_reason"),
            duration_seconds=payload.get("duration"),
            agent_name=runner.get("description"),
            web_url=payload.get("web_url"),
        )

