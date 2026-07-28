import asyncio
import hashlib
import hmac
import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from ci_assistant.domain.ci import RunStatus
from ci_assistant.providers.base import AuthenticationError
from ci_assistant.providers.github.client import repository_path
from ci_assistant.providers.github.provider import GitHubProvider, normalize_status
from ci_assistant.schemas.knowledge import CreateKnowledgeDocument


def test_github_repository_path_requires_owner_and_repository() -> None:
    """验证 GitHub 仓库引用会被安全编码并拒绝非法层级。"""
    assert repository_path("amo/ci assistant") == "/repos/amo/ci%20assistant"
    with pytest.raises(ValueError, match="owner/repository"):
        repository_path("missing-repository")


def test_github_status_mapping_covers_actions_conclusions() -> None:
    """验证 GitHub Actions 状态和结论映射。"""
    assert normalize_status("queued") == RunStatus.QUEUED
    assert normalize_status("in_progress") == RunStatus.RUNNING
    assert normalize_status("completed", "failure") == RunStatus.FAILED
    assert normalize_status("completed", "timed_out") == RunStatus.FAILED
    assert normalize_status("completed", "cancelled") == RunStatus.CANCELED


def test_github_provider_maps_run_jobs_log_changes_and_webhook() -> None:
    """验证 GitHub Actions 只读能力和 Webhook 映射。"""
    client = AsyncMock()
    client.get_workflow_run.return_value = {
        "id": 42,
        "status": "completed",
        "conclusion": "failure",
        "head_branch": "main",
        "head_sha": "abc",
        "html_url": "https://github.example/amo/project/actions/runs/42",
    }
    client.list_workflow_jobs.return_value = [
        {
            "id": 7,
            "run_id": 42,
            "name": "test",
            "status": "completed",
            "conclusion": "failure",
            "started_at": "2026-07-28T01:00:00Z",
            "completed_at": "2026-07-28T01:00:05Z",
            "labels": ["ubuntu-latest"],
        }
    ]
    client.get_job_log.return_value = "0123456789"
    client.get_commit.return_value = {
        "sha": "abc",
        "commit": {
            "message": "Break build\n\nDetails",
            "author": {"name": "Amo"},
        },
        "html_url": "https://github.example/amo/project/commit/abc",
    }
    provider = GitHubProvider(
        "github-main",
        client,
        webhook_secret="secret",
        max_log_chars=5,
    )
    body = json.dumps({"action": "completed"}).encode()
    signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()

    async def exercise():
        """执行 GitHub Provider 的统一契约调用。"""
        run = await provider.get_run("amo/project", "42")
        jobs = await provider.list_jobs("amo/project", "42")
        log = await provider.get_job_log("amo/project", "7")
        changes = await provider.list_changes("amo/project", "42")
        await provider.verify_webhook({"X-Hub-Signature-256": signature}, body)
        event = await provider.parse_webhook(
            {
                "action": "completed",
                "repository": {"full_name": "amo/project"},
                "workflow_run": {
                    "id": 42,
                    "run_attempt": 2,
                    "status": "completed",
                    "conclusion": "failure",
                },
            }
        )
        return run, jobs, log, changes, event

    run, jobs, log, changes, event = asyncio.run(exercise())

    assert run.status == RunStatus.FAILED and run.commit_sha == "abc"
    assert jobs[0].duration_seconds == 5
    assert jobs[0].agent_name == "ubuntu-latest"
    assert log.content == "56789" and log.truncated is True
    assert changes[0].title == "Break build"
    assert event.external_event_id == "workflow_run:42:2:completed"
    assert event.project_ref == "amo/project"
    assert event.status == RunStatus.FAILED


def test_github_webhook_rejects_wrong_signature() -> None:
    """验证 GitHub Webhook 拒绝无效 HMAC 签名。"""
    provider = GitHubProvider("github-main", AsyncMock(), webhook_secret="expected")

    async def verify():
        """提交无效签名供 Provider 校验。"""
        await provider.verify_webhook(
            {"X-Hub-Signature-256": "sha256=invalid"},
            b"{}",
        )

    with pytest.raises(AuthenticationError, match="signature"):
        asyncio.run(verify())


def test_github_workflow_job_webhook_maps_job_and_run_ids() -> None:
    """验证 ``workflow_job`` 事件同时保留 Job 和 Run 标识。"""
    provider = GitHubProvider("github-main", AsyncMock())

    event = asyncio.run(
        provider.parse_webhook(
            {
                "action": "completed",
                "repository": {"full_name": "amo/project"},
                "workflow_job": {
                    "id": 7,
                    "run_id": 42,
                    "run_attempt": 1,
                    "status": "completed",
                    "conclusion": "failure",
                },
            }
        )
    )

    assert event.run_id == "42"
    assert event.job_id == "7"
    assert event.event_type == "workflow_job.completed"


def test_github_knowledge_scope_is_accepted() -> None:
    """验证知识文档可以绑定 GitHub Provider ACL。"""
    payload = CreateKnowledgeDocument(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        provider="github",
        title="GitHub Actions failure",
        format="markdown",
        content="# Failure\nInspect the workflow job log.",
    )

    assert payload.provider == "github"
