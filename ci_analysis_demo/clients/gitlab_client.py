"""
职责是：
    管理 GitLab base_url
    管理 token
    封装 HTTP 请求
    做 timeout
    做异常处理
    返回干净的数据结构
"""
from urllib.parse import quote

import httpx


class GitLabClientError(Exception):
    pass


class GitLabClient:
    def __init__(self, base_url: str, private_token: str, timeout: float = 20):
        self.base_url = base_url.rstrip("/")
        self.private_token = private_token
        self.timeout = timeout

    def _header(self) -> dict:
        return {
            "PRIVATE-TOKEN": self.private_token
        }

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            return await client.get(url, headers=self._header(), params=params)

    async def get_project(self, project_id: str) -> dict:
        """获取 ``get_project`` 对应的数据。"""
        project_id = quote(project_id, safe="")
        resp = await self._get(f"/api/v4/projects/{project_id}")
        if resp.status_code >= 400:
            raise GitLabClientError(f"get_project failed: {resp.status_code} {resp.text[:500]}")

        return resp.json()

    async def get_job(self, project_id: str, job_id: str) -> dict:
        """
        获取job
        :param project_id:
        :param job_id:
        :return:
        """
        project_id = quote(project_id, safe="")
        resp = await self._get(f"/api/v4/projects/{project_id}/jobs/{job_id}")
        if resp.status_code >= 400:
            raise GitLabClientError(f"get_job failed: {resp.status_code} {resp.text[:500]}")

        return resp.json()

    async def get_job_trace(self, project_id: str, job_id: str) -> str:
        """
        获取job的trace内容
        :param project_id:
        :param job_id:
        :return:
        """
        project_id = quote(project_id, safe="")
        resp = await self._get(f"/api/v4/projects/{project_id}/jobs/{job_id}/trace")

        if resp.status_code >= 400:
            raise GitLabClientError(f"get_job_trace failed: {resp.status_code} {resp.text[:500]}")

        return resp.text

    async def get_pipeline(self, project_id: str, pipeline_id: str) -> dict:
        """
        获取pipeline
        :param project_id:
        :param pipeline_id:
        :return:
        """
        project_id = quote(project_id, safe="")
        resp = await self._get(f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}")
        if resp.status_code >= 400:
            raise GitLabClientError(f"get_pipeline failed: {resp.status_code} {resp.text[:500]}")

        return resp.json()

    async def list_pipeline_jobs(self, project_id: str, pipeline_id: str, per_page: int = 20) -> list[dict]:
        """列出 ``list_pipeline_jobs`` 对应的数据。"""
        project_id = quote(project_id, safe="")
        resp = await self._get(
            f"/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
            params={"per_page": per_page},
        )
        if resp.status_code >= 400:
            raise GitLabClientError(f"list_pipeline_jobs failed: {resp.status_code} {resp.text[:500]}")

        return resp.json()

    async def list_commits(
        self,
        project_id: str,
        ref_name: str | None = None,
        per_page: int = 5,
    ) -> list[dict]:
        """列出 ``list_commits`` 对应的数据。"""
        project_id = quote(project_id, safe="")
        params = {"per_page": per_page}
        if ref_name:
            params["ref_name"] = ref_name
        resp = await self._get(f"/api/v4/projects/{project_id}/repository/commits", params=params)
        if resp.status_code >= 400:
            raise GitLabClientError(f"list_commits failed: {resp.status_code} {resp.text[:500]}")

        return resp.json()

    async def get_repository_file_raw(self, project_id: str, file_path: str, ref: str) -> str:
        """获取 ``get_repository_file_raw`` 对应的数据。"""
        project_id = quote(project_id, safe="")
        file_path = quote(file_path, safe="")
        resp = await self._get(
            f"/api/v4/projects/{project_id}/repository/files/{file_path}/raw",
            params={"ref": ref},
        )
        if resp.status_code >= 400:
            raise GitLabClientError(
                f"get_repository_file_raw failed: {resp.status_code} {file_path} {resp.text[:500]}"
            )

        return resp.text
