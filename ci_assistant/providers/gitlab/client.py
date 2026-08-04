from __future__ import annotations

from urllib.parse import quote

import httpx

from ci_assistant.providers.base import (
    AuthenticationError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)


class GitLabClient:
    """封装 GitLab 只读 HTTP 请求，并将上游失败映射为稳定 Provider 异常。"""

    def __init__(self, base_url: str, private_token: str, timeout: float = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.private_token = private_token
        self.timeout = timeout

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers={"PRIVATE-TOKEN": self.private_token},
                    params=params,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderUnavailableError("GitLab request failed") from exc
        if response.status_code in {401, 403}:
            raise AuthenticationError("GitLab authentication failed")
        if response.status_code == 404:
            raise ResourceNotFoundError("GitLab resource not found")
        if response.status_code >= 400:
            raise ProviderUnavailableError(f"GitLab returned HTTP {response.status_code}")
        return response

    async def get_project(self, project_ref: str) -> dict:
        """获取 ``get_project`` 对应的数据。"""
        return (await self._get(f"/api/v4/projects/{quote(project_ref, safe='')}")).json()

    async def get_pipeline(self, project_ref: str, run_id: str) -> dict:
        """获取 ``get_pipeline`` 对应的数据。"""
        project = quote(project_ref, safe="")
        return (await self._get(f"/api/v4/projects/{project}/pipelines/{run_id}")).json()

    async def list_pipeline_jobs(self, project_ref: str, run_id: str) -> list[dict]:
        """列出 ``list_pipeline_jobs`` 对应的数据。"""
        project = quote(project_ref, safe="")
        return (await self._get(f"/api/v4/projects/{project}/pipelines/{run_id}/jobs")).json()

    async def list_project_runners(self, project_ref: str) -> list[dict]:
        """列出项目可用的 Runner，用于识别无匹配 Runner 的排队作业。"""
        project = quote(project_ref, safe="")
        return (
            await self._get(
                f"/api/v4/projects/{project}/runners",
                {"status": "online", "per_page": 100},
            )
        ).json()

    async def get_job(self, project_ref: str, job_id: str) -> dict:
        """获取 ``get_job`` 对应的数据。"""
        project = quote(project_ref, safe="")
        return (await self._get(f"/api/v4/projects/{project}/jobs/{job_id}")).json()

    async def get_job_trace(self, project_ref: str, job_id: str) -> str:
        """获取 ``get_job_trace`` 对应的数据。"""
        project = quote(project_ref, safe="")
        return (await self._get(f"/api/v4/projects/{project}/jobs/{job_id}/trace")).text

    async def list_commits(self, project_ref: str, ref_name: str | None = None) -> list[dict]:
        """列出 ``list_commits`` 对应的数据。"""
        project = quote(project_ref, safe="")
        params = {"ref_name": ref_name} if ref_name else None
        return (await self._get(f"/api/v4/projects/{project}/repository/commits", params)).json()
