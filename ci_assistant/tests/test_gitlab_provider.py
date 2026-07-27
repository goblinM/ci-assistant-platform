import asyncio
from unittest.mock import AsyncMock

from ci_assistant.domain.ci import RunStatus
from ci_assistant.providers.base import AuthenticationError
from ci_assistant.providers.gitlab.provider import GitLabProvider


def test_gitlab_provider_maps_run_job_log_and_webhook() -> None:
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
    provider = GitLabProvider("main", AsyncMock(), webhook_secret="expected")

    async def verify():
        await provider.verify_webhook({"X-Gitlab-Token": "wrong"}, b"{}")

    try:
        asyncio.run(verify())
    except AuthenticationError:
        pass
    else:
        raise AssertionError("invalid webhook token was accepted")

