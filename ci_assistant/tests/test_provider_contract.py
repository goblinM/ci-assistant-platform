import asyncio
from unittest.mock import AsyncMock

from ci_assistant.domain.ci import PipelineRun, RunStatus
from ci_assistant.providers.gitlab.provider import GitLabProvider
from ci_assistant.providers.jenkins.provider import JenkinsProvider


def test_gitlab_and_jenkins_satisfy_run_contract() -> None:
    gitlab_client = AsyncMock()
    gitlab_client.get_pipeline.return_value = {
        "id": 1,
        "status": "failed",
        "ref": "main",
        "sha": "abc",
    }
    jenkins_client = AsyncMock()
    jenkins_client.get_build.return_value = {
        "number": 1,
        "result": "FAILURE",
        "building": False,
    }

    async def load_runs():
        return (
            await GitLabProvider("g", gitlab_client).get_run("p", "1"),
            await JenkinsProvider("j", jenkins_client).get_run("p", "1"),
        )

    runs = asyncio.run(load_runs())
    assert all(isinstance(run, PipelineRun) for run in runs)
    assert {run.status for run in runs} == {RunStatus.FAILED}
    assert {run.provider for run in runs} == {"gitlab", "jenkins"}

