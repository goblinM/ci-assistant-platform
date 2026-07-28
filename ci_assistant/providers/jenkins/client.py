from __future__ import annotations

from urllib.parse import quote

import httpx

from ci_assistant.providers.base import (
    AuthenticationError,
    ProviderUnavailableError,
    ResourceNotFoundError,
)


def job_path(project_ref: str) -> str:
    """执行 ``job_path`` 对应的领域操作。"""
    parts = [part for part in project_ref.split("/") if part]
    return "".join(f"/job/{quote(part, safe='')}" for part in parts)


class JenkinsClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        api_token: str,
        timeout: float = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = (username, api_token)
        self.timeout = timeout

    async def _get(self, path: str) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                auth=self.auth,
                trust_env=False,
            ) as client:
                response = await client.get(f"{self.base_url}{path}")
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderUnavailableError("Jenkins request failed") from exc
        if response.status_code in {401, 403}:
            raise AuthenticationError("Jenkins authentication failed")
        if response.status_code == 404:
            raise ResourceNotFoundError("Jenkins resource not found")
        if response.status_code >= 400:
            raise ProviderUnavailableError(f"Jenkins returned HTTP {response.status_code}")
        return response

    async def get_server(self) -> dict:
        """获取 ``get_server`` 对应的数据。"""
        response = await self._get("/api/json")
        return {
            **response.json(),
            "_jenkins_version": response.headers.get("X-Jenkins"),
        }

    async def get_build(self, project_ref: str, build_id: str) -> dict:
        """获取 ``get_build`` 对应的数据。"""
        response = await self._get(
            f"{job_path(project_ref)}/{quote(build_id, safe='')}/api/json"
        )
        return response.json()

    async def get_console(self, project_ref: str, build_id: str) -> str:
        """获取 ``get_console`` 对应的数据。"""
        return (
            await self._get(
                f"{job_path(project_ref)}/{quote(build_id, safe='')}/consoleText"
            )
        ).text

