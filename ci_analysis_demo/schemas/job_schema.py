from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from .analysis_schema import ToolMode


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_by_alias=True, validate_by_name=True)
    project_name: Annotated[str, Field(max_length=64, min_length=1)]
    branch: Annotated[str, Field(max_length=64, min_length=1)]
    trigger_user: str = Field(alias="triggerUser")
    retry_count: Annotated[int, Field(ge=0, le=3)] = 0

    @field_validator("branch")
    @classmethod
    def check_branch(cls, value: str) -> str:
        if " " in value:
            raise ValueError("branch must not contain spaces")
        return value


class CreatePipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_name: str = Field(min_length=1, max_length=128)
    branch: str = Field(min_length=1, max_length=128)
    retry_count: Annotated[int, Field(ge=0, le=3)] = 0

    @field_validator("branch")
    @classmethod
    def check_branch(cls, value: str) -> str:
        if " " in value:
            raise ValueError("branch must not contain spaces")
        return value


class PipelineResponse(BaseModel):
    pipeline_id: int
    status: str


class AnalyzeGitlabJobRequest(BaseModel):
    # gitlab请求模型
    project_id: str = Field(min_length=1)
    pipeline_id: str | None = None
    job_id: str = Field(min_length=1)
    use_rag: bool = True
    use_tools: bool = Field(
        default=True,
        validation_alias=AliasChoices("use_tools", "use_tool"),
    )
    tool_mode: ToolMode = ToolMode.rule
    request_id: str | None = None


class GitLabJobContext(BaseModel):
    # CI上下文模型
    project_id: str
    pipeline_id: str | None = None
    job_id: str
    job_name: str | None = None
    stage: str | None = None
    status: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    failure_reason: str | None = None
    duration: float | None = None
