from __future__ import annotations

from typing import Any, Protocol

from ci_assistant.domain.ci import (
    CIEvent,
    CommitChange,
    JobRun,
    LogArtifact,
    PipelineRun,
    ProviderCapability,
)


class ProviderError(Exception):
    """统一隔离不同 CI Provider 的可预期失败。"""


class AuthenticationError(ProviderError):
    """表示 Provider 凭据缺失、失效或权限不足。"""

    pass


class ResourceNotFoundError(ProviderError):
    """表示 Provider 中请求的项目、运行或作业不存在。"""

    pass


class ProviderUnavailableError(ProviderError):
    """表示 Provider 网络异常、超时或服务暂时不可用。"""

    pass


class CIProvider(Protocol):
    """定义诊断编排依赖的统一只读 CI 能力与 Webhook 契约。"""

    provider_type: str
    connection_id: str

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        """返回当前 Provider 连接实际支持的只读能力集合。"""
        ...

    async def test_connection(self) -> dict[str, Any]:
        """使用最小请求验证连接、凭据及 Provider 基本可用性。"""
        ...

    async def get_run(self, project_ref: str, run_id: str) -> PipelineRun:
        """获取并映射指定 CI 运行的统一领域数据。"""
        ...

    async def list_jobs(self, project_ref: str, run_id: str) -> list[JobRun]:
        """列出指定 CI 运行中的全部作业并映射为统一模型。"""
        ...

    async def get_job(self, project_ref: str, job_id: str) -> JobRun:
        """获取 Provider 中的指定作业并映射为统一模型。"""
        ...

    async def get_job_log(self, project_ref: str, job_id: str) -> LogArtifact:
        """获取 Provider 中指定作业的受限长度日志产物。"""
        ...

    async def list_changes(self, project_ref: str, run_id: str) -> list[CommitChange]:
        """列出 Provider 中与指定运行关联的代码变更。"""
        ...

    async def verify_webhook(self, headers: dict[str, str], body: bytes) -> None:
        """在解析业务载荷前校验 Webhook 签名或共享密钥。"""
        ...

    async def parse_webhook(self, payload: dict[str, Any]) -> CIEvent:
        """将已验签的 Provider 载荷转换为统一 CI 事件。"""
        ...
