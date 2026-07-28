import asyncio
from unittest.mock import AsyncMock

from ci_assistant.domain.ci import PipelineRun, RunStatus
from ci_assistant.providers.github.provider import GitHubProvider
from ci_assistant.providers.gitlab.provider import GitLabProvider
from ci_assistant.providers.jenkins.provider import JenkinsProvider


def test_all_providers_satisfy_run_contract() -> None:
    """验证 GitLab、Jenkins 和 GitHub 满足统一 Run 契约。"""
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
    github_client = AsyncMock()
    github_client.get_workflow_run.return_value = {
        "id": 1,
        "status": "completed",
        "conclusion": "failure",
        "head_sha": "abc",
    }

    async def load_runs():
        """提供 ``load_runs`` 场景所需的测试替身。"""
        return (
            await GitLabProvider("g", gitlab_client).get_run("p", "1"),
            await JenkinsProvider("j", jenkins_client).get_run("p", "1"),
            await GitHubProvider("gh", github_client).get_run("o/p", "1"),
        )

    runs = asyncio.run(load_runs())
    assert all(isinstance(run, PipelineRun) for run in runs)
    assert {run.status for run in runs} == {RunStatus.FAILED}
    assert {run.provider for run in runs} == {"gitlab", "jenkins", "github"}
