from __future__ import annotations

from urllib.parse import quote

import httpx

from ci_assistant.providers.base import (
    AuthenticationError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)


def repository_path(project_ref: str) -> str:
    """将 ``owner/repository`` 转换为 GitHub REST API 仓库路径。"""
    parts = project_ref.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("GitHub project_ref must use owner/repository format")
    owner, repository = (quote(part, safe="") for part in parts)
    return f"/repos/{owner}/{repository}"


class GitHubClient:
    """封装 GitHub Actions 所需的只读 REST API。"""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def _get(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                trust_env=False,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {self.token}",
                        "X-GitHub-Api-Version": "2026-03-10",
                    },
                    params=params,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderUnavailableError("GitHub request failed") from exc
        if response.status_code in {401, 403}:
            raise AuthenticationError("GitHub authentication failed")
        if response.status_code == 404:
            raise ResourceNotFoundError("GitHub resource not found")
        if response.status_code >= 400:
            raise ProviderUnavailableError(f"GitHub returned HTTP {response.status_code}")
        return response

    async def get_workflow_run(self, project_ref: str, run_id: str) -> dict:
        """获取指定 GitHub Actions Workflow Run。"""
        path = repository_path(project_ref)
        return (await self._get(f"{path}/actions/runs/{quote(run_id, safe='')}")).json()

    async def list_workflow_jobs(self, project_ref: str, run_id: str) -> list[dict]:
        """列出指定 Workflow Run 的全部 Job。"""
        path = repository_path(project_ref)
        response = await self._get(
            f"{path}/actions/runs/{quote(run_id, safe='')}/jobs",
            {"filter": "latest", "per_page": 100},
        )
        return response.json().get("jobs") or []

    async def get_workflow_job(self, project_ref: str, job_id: str) -> dict:
        """获取指定 GitHub Actions Job。"""
        path = repository_path(project_ref)
        return (await self._get(f"{path}/actions/jobs/{quote(job_id, safe='')}")).json()

    async def get_job_log(self, project_ref: str, job_id: str) -> str:
        """下载指定 GitHub Actions Job 的文本日志。"""
        path = repository_path(project_ref)
        return (await self._get(f"{path}/actions/jobs/{quote(job_id, safe='')}/logs")).text

    async def get_commit(self, project_ref: str, commit_sha: str) -> dict:
        """获取 Workflow Run 对应的提交信息。"""
        path = repository_path(project_ref)
        return (await self._get(f"{path}/commits/{quote(commit_sha, safe='')}")).json()
