from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


class ProviderCapability(str, Enum):
    RUN_READ = "run.read"
    JOB_READ = "job.read"
    LOG_READ = "log.read"
    CHANGES_READ = "changes.read"
    REPOSITORY_READ = "repository.read"
    WEBHOOK = "webhook"


class PipelineRun(BaseModel):
    provider: str
    connection_id: str
    project_ref: str
    run_id: str
    status: RunStatus
    branch: str | None = None
    commit_sha: str | None = None
    web_url: str | None = None


class JobRun(BaseModel):
    job_id: str
    run_id: str
    name: str
    stage: str | None = None
    status: RunStatus
    failure_reason: str | None = None
    duration_seconds: float | None = None
    agent_name: str | None = None
    web_url: str | None = None


class LogArtifact(BaseModel):
    job_id: str
    content: str
    truncated: bool = False
    original_length: int = Field(ge=0)


class CommitChange(BaseModel):
    commit_sha: str
    title: str
    message: str | None = None
    author_name: str | None = None
    web_url: str | None = None


class CIEvent(BaseModel):
    provider: str
    external_event_id: str
    event_type: str
    project_ref: str
    run_id: str | None = None
    job_id: str | None = None
    status: RunStatus = RunStatus.UNKNOWN

