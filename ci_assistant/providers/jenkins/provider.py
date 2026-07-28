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

from .client import JenkinsClient


def normalize_status(result: str | None, building: bool = False) -> RunStatus:
    """将 ``normalize_status`` 对应的数据规范化。"""
    if building:
        return RunStatus.RUNNING
    return {
        None: RunStatus.QUEUED,
        "SUCCESS": RunStatus.SUCCESS,
        "FAILURE": RunStatus.FAILED,
        "UNSTABLE": RunStatus.FAILED,
        "ABORTED": RunStatus.CANCELED,
        "NOT_BUILT": RunStatus.SKIPPED,
    }.get(result, RunStatus.UNKNOWN)


class JenkinsProvider:
    provider_type = "jenkins"
    capabilities = frozenset(
        {
            ProviderCapability.RUN_READ,
            ProviderCapability.JOB_READ,
            ProviderCapability.LOG_READ,
            ProviderCapability.CHANGES_READ,
            ProviderCapability.WEBHOOK,
        }
    )

    def __init__(
        self,
        connection_id: str,
        client: JenkinsClient,
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
        server = await self.client.get_server()
        return {
            "ok": True,
            "provider": "jenkins",
            "connection_id": self.connection_id,
            "version": server.get("_jenkins_version"),
            "mode": server.get("mode"),
        }

    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun:
        """获取 ``get_run`` 对应的数据。"""
        build = await self.client.get_build(project_ref, run_id)
        actions = build.get("actions") or []
        branch = self._action_value(actions, "branch")
        commit_sha = self._action_value(actions, "lastBuiltRevision", nested="SHA1")
        return PipelineRun(
            provider="jenkins",
            connection_id=self.connection_id,
            project_ref=project_ref,
            run_id=str(build.get("number", run_id)),
            status=normalize_status(build.get("result"), bool(build.get("building"))),
            branch=branch,
            commit_sha=commit_sha,
            web_url=build.get("url"),
        )

    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]:
        """列出 ``list_jobs`` 对应的数据。"""
        build = await self.client.get_build(project_ref, run_id)
        return [self._map_build(build, run_id)]

    async def get_job(self, project_ref: str, job_id: str) -> JobRun:
        """获取 ``get_job`` 对应的数据。"""
        return self._map_build(await self.client.get_build(project_ref, job_id), job_id)

    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact:
        """获取 ``get_job_log`` 对应的数据。"""
        content = await self.client.get_console(project_ref, job_id)
        return LogArtifact(
            job_id=job_id,
            content=content[-self.max_log_chars :],
            truncated=len(content) > self.max_log_chars,
            original_length=len(content),
        )

    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]:
        """列出 ``list_changes`` 对应的数据。"""
        build = await self.client.get_build(project_ref, run_id)
        items = []
        for change_set in build.get("changeSets") or [build.get("changeSet") or {}]:
            items.extend(change_set.get("items") or [])
        return [
            CommitChange(
                commit_sha=str(item.get("id") or item.get("commitId") or ""),
                title=item.get("msg") or item.get("comment") or "",
                message=item.get("msg"),
                author_name=(item.get("author") or {}).get("fullName"),
                web_url=item.get("url"),
            )
            for item in items
        ]

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None:
        """校验 ``verify_webhook`` 对应的约束。"""
        if self.webhook_secret is None:
            raise AuthenticationError("Jenkins webhook secret is not configured")
        supplied = headers.get("X-Jenkins-Token") or headers.get("x-jenkins-token") or ""
        if not hmac.compare_digest(supplied, self.webhook_secret):
            raise AuthenticationError("Invalid Jenkins webhook token")

    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent:
        """解析或加载 ``parse_webhook`` 对应的数据。"""
        build = payload.get("build") or payload
        project = payload.get("name") or payload.get("job_name") or ""
        build_id = build.get("number") or build.get("id")
        return CIEvent(
            provider="jenkins",
            external_event_id=str(payload.get("event_id") or f"{project}:{build_id}"),
            event_type=str(payload.get("event") or "build"),
            project_ref=str(project),
            run_id=str(build_id) if build_id is not None else None,
            job_id=str(build_id) if build_id is not None else None,
            status=normalize_status(
                build.get("status") or build.get("result"),
                bool(build.get("building")),
            ),
        )

    @staticmethod
    def _map_build(build: dict[str, Any], run_id: str) -> JobRun:
        duration = build.get("duration")
        return JobRun(
            job_id=str(build.get("number", run_id)),
            run_id=run_id,
            name=build.get("fullDisplayName") or build.get("displayName") or "",
            status=normalize_status(build.get("result"), bool(build.get("building"))),
            duration_seconds=(duration / 1000 if duration is not None else None),
            web_url=build.get("url"),
        )

    @staticmethod
    def _action_value(
        actions: list[dict[str, Any]],
        key: str,
        *,
        nested: str | None = None,
    ) -> Any:
        for action in actions:
            if key in action:
                value = action[key]
                return value.get(nested) if nested and isinstance(value, dict) else value
        return None

