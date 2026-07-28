import asyncio
from unittest.mock import AsyncMock

from ci_assistant.domain.ci import RunStatus
from ci_assistant.providers.jenkins.client import job_path
from ci_assistant.providers.jenkins.provider import JenkinsProvider


def test_nested_jenkins_job_path() -> None:
    """验证 ``test_nested_jenkins_job_path`` 所描述的预期行为。"""
    assert job_path("folder/team build") == "/job/folder/job/team%20build"


def test_jenkins_provider_maps_build_log_changes_and_event() -> None:
    """验证 ``test_jenkins_provider_maps_build_log_changes_and_event`` 所描述的预期行为。"""
    client = AsyncMock()
    build = {
        "number": 12,
        "fullDisplayName": "service #12",
        "result": "FAILURE",
        "building": False,
        "duration": 1500,
        "url": "https://jenkins/job/service/12/",
        "changeSet": {
            "items": [
                {
                    "id": "abc",
                    "msg": "break build",
                    "author": {"fullName": "A"},
                }
            ]
        },
    }
    client.get_build.return_value = build
    client.get_console.return_value = "0123456789"
    provider = JenkinsProvider("build", client, webhook_secret="secret", max_log_chars=5)

    async def exercise():
        """提供 ``exercise`` 场景所需的测试替身。"""
        run = await provider.get_run("service", "12")
        jobs = await provider.list_jobs("service", "12")
        log = await provider.get_job_log("service", "12")
        changes = await provider.list_changes("service", "12")
        event = await provider.parse_webhook(
            {"name": "service", "build": {"number": 12, "status": "FAILURE"}}
        )
        return run, jobs, log, changes, event

    run, jobs, log, changes, event = asyncio.run(exercise())

    assert run.status == RunStatus.FAILED
    assert jobs[0].duration_seconds == 1.5
    assert log.content == "56789" and log.truncated is True
    assert changes[0].commit_sha == "abc"
    assert event.external_event_id == "service:12"

