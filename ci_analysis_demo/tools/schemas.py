"""
Tool schema definitions.
统一定义工具元信息
这里描述的是“模型或规则层可见的工具参数”，服务端注入的依赖
例如 gitlab_client 不暴露在 schema 中。
"""

CI_TOOLS_SCHEMA = [
    {
        "name": "query_failure_history",
        "func_name": "query_failure_history",
        "description": "查询项目历史上相似的 CI 失败记录，用于辅助判断故障原因和复用历史修复经验。",
        "provider": "local",
        "tags": ["history", "ci", "diagnosis"],
        "read_only": True,
        "enabled": True,
        "trigger_keywords": [
            "ModuleNotFoundError",
            "ImportError",
            "No module named",
            "403",
            "Forbidden",
            "Unauthorized",
            "AssertionError",
            "SyntaxError",
            "KeyError",
            "timeout",
            "timed out",
            "历史",
            "相似",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "项目名称或项目标识，例如 demo-project。",
                },
                "error_keyword": {
                    "type": "string",
                    "description": "从日志中提取的错误关键词，例如 ModuleNotFoundError、403、AssertionError。",
                },
                "error_type": {
                    "type": "string",
                    "description": "归一化后的错误类型，例如 dependency_missing、repo_auth_failed。",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
        "always_candidate": True,
    },
    {
        "name": "query_pipeline_context",
        "func_name": "query_pipeline_context",
        "description": "查询 GitLab CI pipeline 及其中 job 的上下文信息，例如 pipeline 状态、分支、提交、job 状态和 runner 信息。",
        "provider": "local",
        "tags": ["ci", "gitlab", "pipeline", "job", "context"],
        "read_only": True,
        "enabled": True,
        "trigger_keywords": [
            "pipeline",
            "job",
            "stage",
            "runner",
            "branch",
            "commit",
            "failed",
            "duration",
            "CI",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "GitLab project id 或 URL 编码前的 project path。",
                },
                "pipeline_id": {
                    "type": "string",
                    "description": "GitLab pipeline ID。",
                },
                "job_name": {
                    "type": "string",
                    "description": "CI job 名称，用于从 pipeline jobs 中定位目标 job。",
                },
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
        "always_candidate": False,
    },
    {
        "name": "query_job_context",
        "func_name": "query_job_context",
        "description": "查询指定 GitLab CI job 的必要上下文，例如 job 名称、stage、状态、失败原因、runner、commit。",
        "provider": "local",
        "tags": ["ci", "gitlab", "job", "context"],
        "read_only": True,
        "enabled": True,
        "trigger_keywords": [
            "job",
            "stage",
            "runner",
            "failure_reason",
            "trace",
            "duration",
            "script_failure",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "GitLab project id 或 project path。",
                },
                "job_id": {
                    "type": "string",
                    "description": "GitLab CI job ID。",
                },
            },
            "required": ["project_id", "job_id"],
            "additionalProperties": False,
        },
        "always_candidate": False,
    },
    {
        "name": "check_dependency_file",
        "func_name": "check_dependency_file",
        "description": "检查 GitLab 仓库中的依赖文件是否声明了指定包，适用于 ModuleNotFoundError、依赖缺失等场景。",
        "provider": "local",
        "tags": ["ci", "gitlab", "repository", "dependency"],
        "read_only": True,
        "enabled": True,
        "trigger_keywords": [
            "ModuleNotFoundError",
            "ImportError",
            "No module named",
            "dependency_missing",
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "pip install",
            "依赖",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "GitLab project id 或 project path。",
                },
                "package_name": {
                    "type": "string",
                    "description": "要检查的依赖包名，例如 requests、pytest、uvloop。",
                },
                "ref": {
                    "type": "string",
                    "description": "要检查的分支、tag 或 commit sha；不传则使用项目默认分支。",
                },
            },
            "required": ["project_id", "package_name"],
            "additionalProperties": False,
        },
        "always_candidate": False,
    },
    {
        "name": "query_recent_commits",
        "func_name": "query_recent_commits",
        "description": "查询 GitLab 仓库最近提交，用于判断 CI 失败是否可能与近期代码或依赖变更有关。",
        "provider": "local",
        "tags": ["ci", "gitlab", "repository", "commit", "context"],
        "read_only": True,
        "enabled": True,
        "trigger_keywords": [
            "commit",
            "recent",
            "changed",
            "branch",
            "ref",
            "sha",
            "最近",
            "变更",
            "提交",
        ],
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "GitLab project id 或 project path。",
                },
                "branch": {
                    "type": "string",
                    "description": "分支名；不传则查询默认提交列表。",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回提交数量，建议 1 到 10。",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["project_id"],
            "additionalProperties": False,
        },
        "always_candidate": False,
    },
]


def to_openai_tools_schema() -> list[dict]:
    """转换成 OpenAI-compatible chat.completions tools 格式。"""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in CI_TOOLS_SCHEMA
    ]
