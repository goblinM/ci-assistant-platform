# CI 智能诊断平台开发文档

> 文档状态：评审通过  
> 评审日期：2026-07-24  
> 实施原则：渐进式迁移，保留现有可验证链路

## 1. 开发原则

1. 不一次性重写现有项目。
2. 先建立接口和统一模型，再迁移 GitLab 实现。
3. 业务编排不得直接依赖 GitLab/Jenkins 原始响应。
4. 所有外部调用必须有 timeout、错误映射和 Trace。
5. 默认只读，写操作必须独立声明权限。
6. references 只能由检索层生成。
7. 在线查询和离线知识入库分开运行。
8. 数据表、API 和消息事件都需要版本意识。

## 2. 目标目录

目标目录用于指导迁移，不要求一次完成：

```text
ci_assistant/
├── api/
│   ├── routers/
│   ├── dependencies.py
│   └── errors.py
├── core/
│   ├── config.py
│   ├── logging.py
│   ├── security.py
│   └── telemetry.py
├── domain/
│   ├── ci.py
│   ├── diagnosis.py
│   ├── knowledge.py
│   └── tools.py
├── providers/
│   ├── base.py
│   ├── registry.py
│   ├── gitlab/
│   └── jenkins/
├── diagnosis/
│   ├── orchestrator.py
│   ├── log_preprocessor.py
│   ├── error_detector.py
│   └── policies/
├── llm/
│   ├── gateway.py
│   ├── prompts/
│   └── structured_output.py
├── knowledge/
│   ├── ingestion/
│   ├── chunking/
│   ├── retrieval/
│   └── indexing/
├── tools/
│   ├── executor.py
│   ├── registry.py
│   ├── selectors.py
│   └── builtins/
├── persistence/
│   ├── models/
│   ├── repositories/
│   └── migrations/
├── workers/
│   ├── diagnosis_tasks.py
│   └── ingestion_tasks.py
├── schemas/
├── tests/
└── main.py
```

现有 `ci_analysis_demo` 在迁移完成前继续作为可运行包，不先改包名和所有 import。

### 2.1 项目命名约定

M0 评审确认以下名称：

| 用途 | 名称 | 说明 |
| --- | --- | --- |
| Python 导入包 | `ci_assistant` | 新平台代码的唯一目标包名 |
| Python 发行名 | `ci-assistant-platform` | 用于 `pyproject.toml` 的 `project.name` |
| 服务和容器前缀 | `ci-assistant` | 例如 `ci-assistant-api`、`ci-assistant-worker` |
| 旧兼容包 | `ci_analysis_demo` | 迁移期间保留，完成兼容迁移后删除 |

新代码不得继续增加对 `ci_analysis_demo` 的跨模块依赖。迁移时按模块逐步复制或移动到
`ci_assistant`，旧 API 通过薄适配层保持兼容；不得在一次变更中全局替换包名。

## 3. 配置设计

### 3.1 配置分层

- `.env`：Secret、数据库地址、队列地址和配置文件位置。
- `config.yml`：非敏感系统配置和多个 CI 连接。
- `.ci-assistant.yml`：代码仓库内可选的项目级策略。

示例：

```yaml
app:
  environment: production
  data_dir: /var/lib/ci-assistant

ai:
  provider: openai_compatible
  base_url: ${LLM_API_URL}
  api_key_env: LLM_API_KEY
  model: ${LLM_MODEL}
  timeout_seconds: 30

ci:
  connections:
    - id: corp-gitlab
      type: gitlab
      base_url: https://gitlab.example.com
      token_env: CORP_GITLAB_TOKEN
      webhook_secret_env: CORP_GITLAB_WEBHOOK_SECRET
    - id: build-jenkins
      type: jenkins
      base_url: https://jenkins.example.com
      username_env: JENKINS_USERNAME
      token_env: JENKINS_API_TOKEN

knowledge:
  embedding_model: sentence-transformers/all-MiniLM-L6-v2
  index_backend: faiss
  storage_path: /var/lib/ci-assistant/knowledge
  context_max_chars: 6000
```

配置加载顺序：

```text
代码默认值 < config.yml < 环境变量 < Secret 文件
```

启动时必须验证：

- LLM URL、模型和凭据是否存在。
- 每个 CI Connection ID 唯一。
- Provider 类型是否已注册。
- 数据库和 Redis 是否可连接。
- 知识存储目录是否可写。
- 生产环境不能启用 Uvicorn reload。

## 4. CI 领域模型

### 4.1 Provider 接口

```python
from typing import Protocol


class CIProvider(Protocol):
    provider_type: str

    async def test_connection(self) -> dict: ...
    async def get_run(self, project_ref: str, run_id: str): ...
    async def list_jobs(self, project_ref: str, run_id: str): ...
    async def get_job(self, project_ref: str, job_id: str): ...
    async def get_job_log(self, project_ref: str, job_id: str): ...
    async def list_changes(self, project_ref: str, run_id: str): ...
    async def verify_webhook(self, headers: dict, body: bytes) -> None: ...
    async def parse_webhook(self, payload: dict): ...
```

### 4.2 统一模型

```python
class PipelineRun:
    provider: str
    connection_id: str
    project_ref: str
    run_id: str
    status: str
    branch: str | None
    commit_sha: str | None
    web_url: str | None


class JobRun:
    job_id: str
    run_id: str
    name: str
    stage: str | None
    status: str
    failure_reason: str | None
    duration_seconds: float | None
    agent_name: str | None
```

统一状态值：

```text
created | queued | running | success | failed | canceled | skipped | unknown
```

原始 Provider 响应只允许保存在 Adapter 内部或受控审计字段中，不直接传入 Prompt。

## 5. Provider Registry

```python
class ProviderRegistry:
    def register(self, provider_type: str, factory): ...
    def create(self, connection_config) -> CIProvider: ...
    def supported_types(self) -> list[str]: ...
```

应用启动时遍历配置创建连接，不在 `app.state` 中固定保存单个 `gitlab_client`。

GitLab 迁移步骤：

1. 保留现有 `GitLabClient` HTTP 封装。
2. 新增 `GitLabProvider`，将响应映射到统一模型。
3. 让现有 GitLab Tool 依赖 `CIProvider`。
4. 将 `/analyze-gitlab-job` 迁移到通用 `/diagnoses/runs`。
5. 保留旧接口一段时间并标记 deprecated。

Jenkins 实现步骤：

1. 实现连接测试和鉴权。
2. 实现 Job/Build 基础信息。
3. 实现 Console Log 获取和长度限制。
4. 实现 Changeset。
5. 实现 Webhook/Event 解析。
6. 建立版本、插件和 Job 类型兼容矩阵。

## 6. Tool 平台设计

`ToolSpec` 目标字段：

```python
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict
    func: Callable | None
    executor_kind: str
    ci_provider: str | None
    capabilities: list[str]
    tags: list[str]
    trigger_keywords: list[str]
    read_only: bool
    always_candidate: bool
    enabled: bool
```

选择顺序：

```text
enabled
→ tenant/project policy
→ read_only permission
→ ci_provider
→ capabilities
→ tags
→ trigger_keywords
→ always_candidate
→ max_tools
```

`always_candidate=True` 只绕过日志特征筛选，不能绕过权限、Provider、Capability 和 enabled 校验。

执行前校验：

- 工具名存在。
- 工具在本次候选集合中。
- 参数符合 schema。
- 当前项目允许该工具。
- Provider 连接属于当前租户和项目。
- 调用次数没有超限。

## 7. 诊断编排

```text
1. 接收 Manual/Webhook 请求
2. 读取项目和 Provider 上下文
3. 获取或接收原始日志
4. 日志脱敏和关键片段提取
5. 识别 primary_error
6. 构建 RAG query 和 metadata filters
7. 检索知识
8. 动态选择并执行只读工具
9. 构建最终 Prompt
10. 调用 LLM 并校验结构
11. 保存 references、trace 和结果
12. 返回或通知调用方
```

Warp Skill 中的“先检查状态、再收集失败日志、最后生成计划”应实现为 `DiagnosisPolicy`，不与具体 GitHub CLI 绑定。

## 8. 知识入库

### 8.1 文档状态

```text
uploaded → validating → indexing → draft → active
                                  ↘ failed
active → superseded | deleted
```

只有 `active` 文档可以参与在线检索。

### 8.2 Chunk 策略

优先按文档结构切片：

1. 标题和章节。
2. 错误现象。
3. 根因。
4. 排查步骤。
5. 解决方案。
6. 验证方式。

首期建议：

- 每个 Chunk 约 300 到 800 个中文字符。
- 相邻 Chunk 保留少量重叠。
- 堆栈、命令和代码块尽量不拆开。
- 标题、错误类型和来源进入每个 Chunk Metadata。
- Parent Document 与 Chunk 分开保存。

### 8.3 索引

MVP 保留 SentenceTransformer 和 FAISS，增加：

- Embedding 模型配置化。
- 向量和 Metadata 持久化。
- `IndexIDMap2` 或等价稳定 ID 映射。
- 按租户或知识空间隔离索引。
- 增量新增和删除标记。
- 索引版本目录和原子切换。
- 应用启动时加载索引，不重新计算全部向量。

后续知识规模和过滤需求增加后，再评估 pgvector、Qdrant、Milvus 或 OpenSearch，不在 MVP 同时维护多个向量后端。

### 8.4 在线检索

```text
clean log
→ query rewrite
→ semantic top N
→ keyword top N
→ metadata top N
→ merge and deduplicate
→ ACL filter
→ rule rerank
→ final top K
→ context budget
```

RAG Trace 必须记录：

- query
- filters
- top_k
- candidate_count
- hit_doc_ids
- hit_titles
- scores
- retrieval_sources
- duration_ms
- context_length
- index_version

## 9. 数据持久化

建议 PostgreSQL 保存业务数据，Redis 保存任务队列和短期锁，原始文件保存在本地挂载目录或兼容对象存储。

关键约束：

- `ci_events(provider, connection_id, external_event_id)` 唯一。
- `diagnoses.trace_id` 唯一。
- Knowledge Document 使用逻辑删除，并触发索引删除任务。
- Secret 不写入数据库业务字段。
- 原始日志是否保存由客户策略控制，默认只保存脱敏摘要。
- Trace 中的大字段需要设置长度上限。

## 10. API 约定

响应使用统一 Envelope：

```json
{
  "request_id": "req_xxx",
  "data": {},
  "error": null
}
```

异步诊断：

```json
{
  "request_id": "req_xxx",
  "data": {
    "diagnosis_id": "diag_xxx",
    "status": "queued"
  },
  "error": null
}
```

错误类型：

- `CONFIG_INVALID`
- `AUTH_FAILED`
- `PERMISSION_DENIED`
- `PROVIDER_UNAVAILABLE`
- `RESOURCE_NOT_FOUND`
- `WEBHOOK_INVALID`
- `KNOWLEDGE_INVALID`
- `LLM_UNAVAILABLE`
- `LLM_RESPONSE_INVALID`
- `DIAGNOSIS_FAILED`

## 11. 安全设计

- Provider Token 使用最小只读权限。
- Webhook 请求先验证，再解析业务字段。
- URL 和连接配置防止 SSRF。
- 上传文件限制类型、大小和数量。
- 知识和日志都视为不可信内容。
- Prompt 明确区分系统指令、日志、知识和 Tool Result。
- Tool Result 只保留必要字段。
- 任何写工具都需要 `read_only=False`、权限策略和人工确认。
- LLM 请求前再次执行 Secret Mask。

## 12. 测试策略

单元测试：

- Provider 字段映射。
- Webhook 验证和事件解析。
- 日志提取、脱敏和错误识别。
- Tool 选择、权限和参数校验。
- Chunk、Metadata、去重和索引版本。
- LLM 结构解析和 fallback。

契约测试：

- 使用固定 GitLab/Jenkins JSON Fixture。
- 每个 Provider 对同一领域模型满足一致约束。
- 外部 API 错误映射稳定。

集成测试：

- API + PostgreSQL + Redis + Worker。
- Webhook 到诊断结果完整链路。
- 上传文档到可检索引用完整链路。

评测：

- 固定基线集不随 Prompt 修改而静默变化。
- 按 Provider、error_type、是否 RAG、是否 Tool 分组。
- 保存每次模型、Prompt、知识索引和代码版本。

## 13. 迁移阶段

### 阶段 A：建立平台骨架

- 新配置结构。
- PostgreSQL、Redis、迁移和健康检查。
- 诊断记录持久化。

### 阶段 B：Provider 抽象

- 统一领域模型和 Registry。
- GitLab Client 迁入 GitLab Provider。
- 旧 GitLab API 兼容。

### 阶段 C：事件和 Jenkins

- Webhook 幂等和 Worker。
- Jenkins Provider。
- GitLab/Jenkins 契约测试。

### 阶段 D：知识平台

- 文档上传、Chunk、版本和索引发布。
- 租户/项目过滤。
- 持久化 FAISS。

### 阶段 E：质量和交付

- 完整评测、监控、审计和安全测试。
- Docker Compose 一键启动。
- 安装、配置、升级和故障排查文档。

具体状态见 [开发跟进文档](ci_assistant_platform_tracker.md)。
