from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
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

from .client import GitHubClient


_CONCLUSION_MAP = {
    "success": RunStatus.SUCCESS,
    "failure": RunStatus.FAILED,
    "timed_out": RunStatus.FAILED,
    "startup_failure": RunStatus.FAILED,
    "cancelled": RunStatus.CANCELED,
    "skipped": RunStatus.SKIPPED,
    "neutral": RunStatus.SKIPPED,
}


def normalize_status(status: str | None, conclusion: str | None = None) -> RunStatus:
    """将 GitHub Actions 状态和结论映射到统一运行状态。"""
    if conclusion:
        return _CONCLUSION_MAP.get(conclusion, RunStatus.UNKNOWN)
    return {
        "requested": RunStatus.CREATED,
        "waiting": RunStatus.QUEUED,
        "pending": RunStatus.QUEUED,
        "queued": RunStatus.QUEUED,
        "in_progress": RunStatus.RUNNING,
        "completed": RunStatus.UNKNOWN,
    }.get(status or "", RunStatus.UNKNOWN)


class GitHubProvider:
    """将 GitHub Actions 映射到统一只读 CI Provider。"""

    provider_type = "github"
    capabilities = frozenset(
        {
            ProviderCapability.RUN_READ,
            ProviderCapability.JOB_READ,
            ProviderCapability.LOG_READ,
            ProviderCapability.CHANGES_READ,
            ProviderCapability.REPOSITORY_READ,
            ProviderCapability.WEBHOOK,
        }
    )

    def __init__(
        self,
        connection_id: str,
        client: GitHubClient,
        *,
        webhook_secret: str | None = None,
        max_log_chars: int = 200_000,
    ) -> None:
        self.connection_id = connection_id
        self.client = client
        self.webhook_secret = webhook_secret
        self.max_log_chars = max_log_chars

    async def test_connection(self) -> dict[str, Any]:
        """返回 GitHub Provider 的连接配置状态。"""
        return {
            "ok": True,
            "provider": "github",
            "connection_id": self.connection_id,
        }

    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun:
        """获取并映射 GitHub Actions Workflow Run。"""
        payload = await self.client.get_workflow_run(project_ref, run_id)
        return PipelineRun(
            provider="github",
            connection_id=self.connection_id,
            project_ref=project_ref,
            run_id=str(payload["id"]),
            status=normalize_status(payload.get("status"), payload.get("conclusion")),
            branch=payload.get("head_branch"),
            commit_sha=payload.get("head_sha"),
            web_url=payload.get("html_url"),
        )

    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]:
        """列出并映射 Workflow Run 下的 GitHub Actions Job。"""
        payloads = await self.client.list_workflow_jobs(project_ref, run_id)
        return [self._map_job(payload, run_id) for payload in payloads]

    async def get_job(self, project_ref: str, job_id: str) -> JobRun:
        """获取并映射指定 GitHub Actions Job。"""
        payload = await self.client.get_workflow_job(project_ref, job_id)
        return self._map_job(payload, str(payload.get("run_id") or ""))

    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact:
        """获取指定 GitHub Actions Job 日志，保留尾部并记录是否截断。"""
        content = await self.client.get_job_log(project_ref, job_id)
        return LogArtifact(
            job_id=job_id,
            content=content[-self.max_log_chars :],
            truncated=len(content) > self.max_log_chars,
            original_length=len(content),
        )

    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]:
        """获取 Workflow Run 的 Head Commit。"""
        run = await self.get_run(project_ref, run_id)
        if not run.commit_sha:
            return []
        payload = await self.client.get_commit(project_ref, run.commit_sha)
        commit = payload.get("commit") or {}
        message = commit.get("message") or ""
        author = commit.get("author") or {}
        return [
            CommitChange(
                commit_sha=str(payload.get("sha") or run.commit_sha),
                title=message.splitlines()[0] if message else "",
                message=message or None,
                author_name=author.get("name"),
                web_url=payload.get("html_url"),
            )
        ]

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None:
        """校验 GitHub Webhook 的 HMAC-SHA256 签名。"""
        if self.webhook_secret is None:
            raise AuthenticationError("GitHub webhook secret is not configured")
        supplied = (
            headers.get("X-Hub-Signature-256")
            or headers.get("x-hub-signature-256")
            or ""
        )
        expected = "sha256=" + hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise AuthenticationError("Invalid GitHub webhook signature")

    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent:
        """解析 GitHub ``workflow_run`` 或 ``workflow_job`` Webhook。"""
        event_name, item = self._event_payload(payload)
        repository = payload.get("repository") or {}
        run_id = item.get("run_id") if event_name == "workflow_job" else item.get("id")
        job_id = item.get("id") if event_name == "workflow_job" else None
        attempt = item.get("run_attempt") or 1
        action = str(payload.get("action") or "unknown")
        return CIEvent(
            provider="github",
            external_event_id=f"{event_name}:{item.get('id')}:{attempt}:{action}",
            event_type=f"{event_name}.{action}",
            project_ref=str(repository.get("full_name") or ""),
            run_id=str(run_id) if run_id is not None else None,
            job_id=str(job_id) if job_id is not None else None,
            status=normalize_status(item.get("status"), item.get("conclusion")),
        )

    @staticmethod
    def _event_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        if isinstance(payload.get("workflow_run"), dict):
            return "workflow_run", payload["workflow_run"]
        if isinstance(payload.get("workflow_job"), dict):
            return "workflow_job", payload["workflow_job"]
        return "unknown", {}

    @staticmethod
    def _map_job(payload: dict[str, Any], run_id: str) -> JobRun:
        labels = payload.get("labels") or []
        return JobRun(
            job_id=str(payload["id"]),
            run_id=run_id,
            name=payload.get("name") or "",
            status=normalize_status(payload.get("status"), payload.get("conclusion")),
            duration_seconds=GitHubProvider._duration_seconds(
                payload.get("started_at"),
                payload.get("completed_at"),
            ),
            agent_name=", ".join(str(label) for label in labels) or None,
            web_url=payload.get("html_url"),
        )

    @staticmethod
    def _duration_seconds(started_at: str | None, completed_at: str | None) -> float | None:
        if not started_at or not completed_at:
            return None
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max((end - start).total_seconds(), 0)
