# CI 智能诊断平台 MVP

> 文档状态：评审通过  
> 目标版本：`0.5.0`  
> 基线日期：2026-07-24  
> 评审日期：2026-07-24

## 1. MVP 目标

交付一套可以在客户内网通过 Docker Compose 启动的 CI 智能诊断服务。客户完成 AI、GitLab、Jenkins 和存储配置后，可以通过 API 或 Webhook 分析失败任务，并使用公共知识和客户私有知识生成带引用的结构化诊断结果。

一句话验收标准：

> 一套部署连接 GitLab 和 Jenkins，失败事件可以稳定进入统一诊断链路，诊断结果可追踪、可引用、可评测，客户知识可增量上传和删除。

## 2. 目标用户

- 开发工程师：获得失败原因、证据和可执行建议。
- DevOps 工程师：连接 CI、维护项目知识和查看诊断轨迹。
- 平台管理员：管理模型、连接、权限、知识来源和审计。

## 3. 核心使用流程

### 3.1 手动分析

```text
提交日志或 CI Run 标识
→ 校验项目权限
→ 获取并清洗日志
→ RAG 和 Tool Calling
→ 返回结构化诊断
→ 保存诊断记录
```

### 3.2 Webhook 自动分析

```text
GitLab Job/Pipeline Failed 或 Jenkins Build Failed
→ 校验 Webhook
→ 创建幂等事件
→ Worker 获取日志和上下文
→ 执行诊断
→ 保存结果
→ 可选发送通知
```

### 3.3 私有知识上传

```text
管理员上传 Markdown/JSON
→ 校验文档结构和作用域
→ 清洗、切片、去重
→ 后台生成 Embedding
→ 发布新索引版本
→ 后续诊断可检索引用
```

## 4. MVP 功能范围

### 4.1 部署与配置

- 提供 `docker-compose.yml`。
- 提供 `api`、`worker`、`postgres`、`redis` 服务。
- 提供 `.env.example` 和配置校验。
- 提供 `/health/live` 和 `/health/ready`。
- 支持 OpenAI-compatible LLM API。
- 支持外部 LLM 和客户内网兼容模型地址。
- 所有 Secret 通过环境变量或 Secret 文件注入。

### 4.2 CI Provider

GitLab：

- Project、Pipeline、Job、Trace、Commit、Repository File 读取。
- Pipeline 和 Job Webhook。
- Token 或 Project Access Token。

Jenkins：

- Job、Build、Build Result、Console Log、Changeset 读取。
- Build 完成事件接入。
- 用户名和 API Token 鉴权。
- 支持普通 Job 和 Pipeline Job 的基础能力。

通用能力：

- Provider 连接测试。
- Provider Capability 声明。
- 统一 `PipelineRun`、`JobRun` 和 `LogArtifact`。
- 默认只开放读取能力。

### 4.3 诊断能力

- 纯 LLM、RAG、规则 Tool、自主 Tool Calling 模式。
- 日志长度限制、关键行提取和敏感信息脱敏。
- Primary Error 识别。
- 候选工具动态过滤。
- 模型 Tool Call 参数校验。
- 最多工具调用次数限制。
- 结构化响应校验、重试和 fallback。
- references 必须来自真实检索结果。
- AnalysisTrace 记录检索、工具和模型信息。

### 4.4 知识库

- 公共知识和客户私有知识分开管理。
- 首期支持 Markdown 和 JSON。
- 文档结构校验。
- 文档版本、状态、来源和许可证记录。
- 文档作用域：全局、Provider、项目。
- Chunk、Embedding、增量索引和删除。
- Semantic、Keyword、Metadata 多路召回。
- 规则 Rerank 和上下文预算。
- 检索结果必须受 tenant/project ACL 过滤。

### 4.5 数据和审计

- 保存 CI 连接、项目映射、事件、诊断、Trace、知识文档和 Chunk。
- 保存 Prompt 版本、模型名称和索引版本。
- 敏感日志不默认保存全文。
- Webhook、诊断任务和知识任务具有幂等键。
- 所有失败任务记录可重试原因。

### 4.6 API

首期 API：

```text
POST   /api/v1/diagnoses/logs
POST   /api/v1/diagnoses/runs
GET    /api/v1/diagnoses/{diagnosis_id}

POST   /api/v1/connections/test
GET    /api/v1/connections

POST   /api/v1/knowledge/documents
GET    /api/v1/knowledge/documents
GET    /api/v1/knowledge/documents/{document_id}
DELETE /api/v1/knowledge/documents/{document_id}
POST   /api/v1/knowledge/reindex

POST   /api/v1/webhooks/{connection_id}/gitlab
POST   /api/v1/webhooks/{connection_id}/jenkins

GET    /health/live
GET    /health/ready
```

## 5. MVP 非功能要求

### 5.1 可靠性

- 相同 Webhook 事件不得重复创建诊断。
- Provider、LLM、Embedding 服务均配置超时和有限重试。
- 单个 Tool 失败不能导致整个进程退出。
- Worker 重启后未完成任务可以继续执行。
- RAG 不可用时可以降级为无 RAG 诊断。

### 5.2 性能

- API 接收 Webhook 后 2 秒内返回已接收。
- 普通日志诊断 P95 在 30 秒内完成，不包含外部 Provider 长时间阻塞。
- 单次 LLM Context 有明确字符或 Token 预算。
- 知识索引更新不阻塞在线查询。

### 5.3 安全

- CI 和 LLM Token 不出现在响应、Prompt、Trace 和普通日志中。
- 默认工具全部只读。
- Webhook 必须验证 Secret 或签名。
- 文档检索必须带租户和项目作用域。
- 上传内容按不可信输入处理。
- 所有 Tool 参数在执行前通过 JSON Schema 或 Pydantic 校验。

### 5.4 可观测性

- 日志包含 `trace_id`、`diagnosis_id`、`connection_id` 和 `provider`。
- 记录 Provider、RAG、Tool、LLM 各阶段耗时。
- 暴露任务成功率、失败率和诊断耗时指标。
- 错误日志不能包含 Secret 和完整敏感 CI 日志。

## 6. 数据模型最小集合

| 实体 | 用途 |
| --- | --- |
| `tenants` | 客户或部署空间 |
| `ci_connections` | GitLab/Jenkins 连接和非敏感配置 |
| `projects` | 平台项目与 CI 项目映射 |
| `ci_events` | Webhook 事件和幂等状态 |
| `diagnoses` | 结构化诊断结果 |
| `analysis_traces` | RAG、Tool、LLM 轨迹 |
| `knowledge_documents` | 知识文档和版本 |
| `knowledge_chunks` | Chunk、Metadata 和索引引用 |
| `ingestion_jobs` | 知识入库任务 |
| `evaluation_runs` | 评测执行和指标 |

## 7. MVP 质量指标

离线质量：

- Schema valid rate：100%。
- Error type accuracy：不低于当前稳定基线。
- Reference hit rate：按 Provider 和 error_type 分组统计。
- Keyword score：按错误类型统计，不只看总平均。
- Tool success rate：成功工具数 / 实际调用工具数。

在线质量：

- Webhook 去重成功率。
- 诊断成功率和 fallback rate。
- Provider API 失败率。
- RAG 空召回率和引用覆盖率。
- 用户 helpful/not helpful 反馈。
- 单次诊断模型调用次数和成本。

MVP 上线前必须建立固定回归集，GitLab 和 Jenkins 各至少覆盖：

- 依赖缺失
- 依赖冲突
- 测试失败
- 权限或认证失败
- 网络超时
- Runner/Agent 不可用
- Docker 构建失败
- 资源不足
- 未知错误

## 8. Definition of Done

MVP 完成必须同时满足：

- [x] 新环境执行一条 Docker Compose 命令可以启动全部服务。
- [x] 缺少必要配置时启动失败信息清晰。
- [x] GitLab 和 Jenkins 连接测试能力通过契约测试。
- [x] 两种 Provider 的失败事件均能生成统一诊断。
- [x] 手动日志分析兼容当前 API 核心能力。
- [x] 诊断结果、references 和 trace 可以持久化查询。
- [x] Markdown/JSON 知识可以上传、更新、检索和删除。
- [x] 客户知识不会跨项目或租户召回。
- [x] 所有默认工具只读，Tool 参数经过校验。
- [x] 单元测试、集成测试和固定评测集通过。
- [x] README 包含安装、配置、Webhook、知识上传和排障说明。
- [x] 数据来源和第三方许可证有记录。

## 9. 版本后置能力

`0.6.x`：

- GitHub Actions Provider。
- PDF、DOCX、HTML 解析。
- Cross-Encoder/BGE Reranker。
- Web 管理页面。

`0.7.x`：

- 历史失败相似检索。
- 用户反馈驱动的评测集更新。
- 通知到 GitLab Comment、Slack、邮件等。

`1.0` 前：

- 受控写工具。
- 人工审批后重跑 CI、创建 Issue 或提交修复建议。
- 高可用部署、Helm Chart 和外部 Secret Manager。

## 10. 相关文档

- [当前架构](architecture.md)
- [工程决策](DECISIONS.md)
- [当前待办](TODO.md)
- [MVP 验收记录](mvp_acceptance_report.md)
