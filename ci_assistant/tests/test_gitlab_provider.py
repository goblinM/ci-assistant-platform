import asyncio
from unittest.mock import AsyncMock

from ci_assistant.domain.ci import RunStatus
from ci_assistant.providers.base import AuthenticationError
from ci_assistant.providers.gitlab.provider import GitLabProvider


def test_gitlab_provider_maps_run_job_log_and_webhook() -> None:
    """验证 ``test_gitlab_provider_maps_run_job_log_and_webhook`` 所描述的预期行为。"""
    client = AsyncMock()
    client.get_pipeline.return_value = {
        "id": 42,
        "status": "failed",
        "ref": "main",
        "sha": "abc",
        "web_url": "https://gitlab/p/42",
    }
    client.list_pipeline_jobs.return_value = [
        {"id": 7, "name": "test", "status": "failed", "runner": {"description": "r1"}}
    ]
    client.get_job_trace.return_value = "x" * 20
    provider = GitLabProvider("main", client, webhook_secret="secret", max_log_chars=10)

    async def exercise():
        """提供 ``exercise`` 场景所需的测试替身。"""
        run = await provider.get_run("group/project", "42")
        jobs = await provider.list_jobs("group/project", "42")
        log = await provider.get_job_log("group/project", "7")
        await provider.verify_webhook({"X-Gitlab-Token": "secret"}, b"{}")
        event = await provider.parse_webhook(
            {
                "object_kind": "pipeline",
                "project": {"path_with_namespace": "group/project"},
                "object_attributes": {"id": 42, "status": "failed"},
            }
        )
        return run, jobs, log, event

    run, jobs, log, event = asyncio.run(exercise())

    assert run.status == RunStatus.FAILED
    assert jobs[0].agent_name == "r1"
    assert log.truncated is True and log.original_length == 20
    assert event.run_id == "42" and event.status == RunStatus.FAILED


def test_gitlab_webhook_rejects_wrong_secret() -> None:
    """验证 ``test_gitlab_webhook_rejects_wrong_secret`` 所描述的预期行为。"""
    provider = GitLabProvider("main", AsyncMock(), webhook_secret="expected")

    async def verify():
        """提供 ``verify`` 场景所需的测试替身。"""
        await provider.verify_webhook({"X-Gitlab-Token": "wrong"}, b"{}")

    try:
        asyncio.run(verify())
    except AuthenticationError:
        pass
    else:
        raise AssertionError("invalid webhook token was accepted")


def test_gitlab_pending_pipeline_detects_unmatched_runner_tags() -> None:
    """验证 pending 作业没有兼容在线 Runner 时生成诊断原因。"""
    client = AsyncMock()
    client.list_pipeline_jobs.return_value = [
        {
            "id": 9,
            "name": "test",
            "status": "pending",
            "tag_list": ["docker"],
        }
    ]
    client.list_project_runners.return_value = [
        {
            "id": 3,
            "status": "online",
            "paused": False,
            "run_untagged": True,
            "tag_list": ["shell"],
        }
    ]
    provider = GitLabProvider("main", client, webhook_secret="secret")

    event = asyncio.run(
        provider.parse_webhook(
            {
                "object_kind": "pipeline",
                "project": {"path_with_namespace": "group/project"},
                "object_attributes": {"id": 42, "status": "pending"},
            }
        )
    )

    assert event.status == RunStatus.QUEUED
    assert event.diagnostic_reason == "runner_unavailable"


def test_gitlab_pending_pipeline_accepts_compatible_runner() -> None:
    """验证存在兼容在线 Runner 时 pending 流水线保持正常排队。"""
    client = AsyncMock()
    client.list_pipeline_jobs.return_value = [
        {
            "id": 9,
            "name": "test",
            "status": "pending",
            "tag_list": ["docker"],
        }
    ]
    client.list_project_runners.return_value = [
        {
            "id": 3,
            "status": "online",
            "paused": False,
            "run_untagged": False,
            "tag_list": ["docker", "linux"],
        }
    ]
    provider = GitLabProvider("main", client, webhook_secret="secret")

    event = asyncio.run(
        provider.parse_webhook(
            {
                "object_kind": "pipeline",
                "project": {"path_with_namespace": "group/project"},
                "object_attributes": {"id": 42, "status": "pending"},
            }
        )
    )

    assert event.status == RunStatus.QUEUED
    assert event.diagnostic_reason is None
