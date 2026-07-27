# CI 智能诊断平台开发跟进

> 最后更新：2026-07-25  
> 当前阶段：M5 MVP 验收完成  
> 目标版本：`0.5.0`

## 1. 状态说明

| 状态 | 含义 |
| --- | --- |
| `已完成` | 已实现并有基本验证 |
| `进行中` | 已开始实施，尚未满足 Definition of Done |
| `待办` | 已确认进入 MVP，尚未实施 |
| `后置` | 不属于当前 MVP |
| `阻塞` | 需要外部条件或决策 |

更新规则：

1. 每次开发只允许少量事项处于 `进行中`。
2. 状态变更时同步填写完成证据或阻塞原因。
3. 功能完成但没有测试时不能标记为 `已完成`。
4. 新增范围先更新 MVP 文档，再进入本跟进表。
5. 每个阶段完成后运行固定评测并记录结果。

## 2. 当前能力快照

| 能力 | 状态 | 证据或说明 |
| --- | --- | --- |
| FastAPI 平台服务 | 已完成 | `ci_assistant/main.py` 与 `/api/v1` |
| 统一日志/Run 诊断 | 已完成 | `/api/v1/diagnoses/logs`、`/runs` |
| 结构化诊断 | 已完成 | OpenAI-compatible/规则网关、Pydantic 校验和 fallback |
| GitLab Provider | 已完成 | Run、Job、Trace、Change、Webhook 与 Capability |
| Jenkins Provider | 已完成 | 普通/嵌套 Job、Build、Console、Changeset 与 Webhook |
| 只读 Tool 策略 | 已完成 | Capability、参数模型、项目允许列表和调用上限 |
| PostgreSQL/Alembic | 已完成 | 核心、知识和评测实体持久化 |
| Redis/Celery | 已完成 | diagnosis/knowledge 隔离队列、重试和 late ack |
| 知识平台 | 已完成 | Markdown/JSON、Chunk、去重、版本和逻辑删除 |
| 混合检索 | 已完成 | Semantic、Keyword、Metadata 与 ACL |
| FAISS 发布 | 已完成 | 版本目录、原子 `CURRENT` 与 Docker 持久卷 |
| AnalysisTrace | 已完成 | RAG、Tool、LLM 调用信息持久化 |
| 鉴权与租户 ACL | 已完成 | Bearer Key、管理员边界、tenant/project/provider 过滤 |
| Docker Compose | 已完成 | 五服务实际启动和健康验证 |
| 固定评测 | 已完成 | GitLab/Jenkins 18 Case、9 类错误 |

## 3. 里程碑

| 里程碑 | 目标 | 状态 |
| --- | --- | --- |
| M0 设计冻结 | 可行性、MVP、开发和跟进文档评审完成 | 已完成 |
| M1 平台骨架 | 配置、数据库、队列、健康检查可运行 | 已完成 |
| M2 GitLab Provider | GitLab 通过统一 Provider 完成诊断 | 已完成 |
| M3 Jenkins Provider | Jenkins 通过统一 Provider 完成诊断 | 已完成 |
| M4 知识平台 | 私有知识可上传、索引、检索和删除 | 已完成 |
| M5 MVP 验收 | Docker Compose、测试、评测、安全文档完成 | 已完成 |

## 4. M0 设计冻结

| ID | 事项 | 状态 | 完成标准 |
| --- | --- | --- | --- |
| M0-01 | 产品化可行性分析 | 已完成 | 明确产品形态、边界、风险和 Skill 关系 |
| M0-02 | MVP 范围 | 已完成 | 功能和非功能范围、DoD 明确 |
| M0-03 | 开发设计 | 已完成 | 模块、接口、数据和迁移顺序明确 |
| M0-04 | 开发跟进机制 | 已完成 | 状态、里程碑和任务表建立 |
| M0-05 | 用户评审四份文档 | 已完成 | 范围、边界、架构和迁移顺序评审通过 |
| M0-06 | 确定新项目包名 | 已完成 | 导入包 `ci_assistant`，发行名 `ci-assistant-platform` |
| M0-07 | 确定 MVP 持久化方案 | 已完成 | PostgreSQL 存业务数据、Redis 存队列和短期锁、FAISS 持久化向量索引 |

## 5. M1 平台骨架

| ID | 事项 | 状态 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- |
| M1-01 | 增加 `pyproject.toml` | 已完成 | M0 | `ci-assistant-platform` 元数据、运行/开发依赖、包发现和 pytest 配置已建立；11 项测试通过 |
| M1-02 | 配置模型分层 | 已完成 | M0 | 支持代码默认值、YAML、env、Secret 文件依次覆盖；连接 ID、URL 和生产环境配置已校验；16 项测试通过 |
| M1-03 | PostgreSQL 数据层 | 已完成 | M0 | SQLAlchemy 异步 Engine、事务 Session、声明式模型基类和通用 Repository 可用；19 项测试通过 |
| M1-04 | 数据库迁移 | 已完成 | M1-03 | Alembic 异步迁移环境和核心平台表首个 revision 已建立 |
| M1-05 | Redis 和 Worker | 已完成 | M0 | Celery 使用 Redis broker/backend，late ack、Worker 丢失重入队、有限重试和队列隔离已配置 |
| M1-06 | 健康检查 | 已完成 | M1-03、M1-05 | `/health/live` 与 `/health/ready` 已区分，ready 并发检查 PostgreSQL 和 Redis |
| M1-07 | 统一错误响应 | 已完成 | M0 | 新 API 使用统一 Envelope、稳定错误码和 request_id |
| M1-08 | 诊断结果持久化 | 已完成 | M1-03 | Diagnosis/AnalysisTrace 模型、生命周期 Repository、创建与查询 API 已实现 |
| M1-09 | Docker Compose | 已完成 | M1-03、M1-05 | API、Worker、Migration、PostgreSQL、Redis、健康检查和持久卷已定义 |
| M1-10 | 平台骨架集成测试 | 已完成 | M1-01 至 M1-09 | Compose 实际启动 API、Worker、Migration、PostgreSQL、Redis；ready 返回 DB/Redis `ok`，Worker 以 uid 999 运行 |

## 6. M2 GitLab Provider

| ID | 事项 | 状态 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- |
| M2-01 | 定义 CI 领域模型 | 已完成 | M1 | Run、Job、Log、Change、Event 和统一状态已实现 |
| M2-02 | 定义 CIProvider Protocol | 已完成 | M2-01 | 核心读能力、Webhook、Capability 和稳定异常边界已定义 |
| M2-03 | Provider Registry | 已完成 | M2-02 | 支持注册、重复保护、按连接配置创建和类型查询 |
| M2-04 | GitLabProvider | 已完成 | M2-03 | 独立 GitLab Client 已迁入新包并映射统一模型 |
| M2-05 | GitLab Capability | 已完成 | M2-04 | GitLab Provider 声明 Run/Job/Log/Change/Repository/Webhook 能力 |
| M2-06 | Tool 依赖改造 | 已完成 | M2-04 | 新 Tool Executor 只依赖 CIProvider，按 Capability、只读策略和项目允许列表过滤 |
| M2-07 | GitLab Webhook 验证 | 已完成 | M1、M2-04 | 共享 Token 常量时间校验和事件统一映射已实现 |
| M2-08 | Webhook 幂等 | 已完成 | M2-07 | PostgreSQL `ON CONFLICT DO NOTHING` 保证重复事件不创建诊断 |
| M2-09 | 通用 Run 诊断 API | 已完成 | M2-04 | `/api/v1/diagnoses/runs` 面向连接和统一 Provider |
| M2-10 | 旧接口兼容测试 | 已完成 | M2-09 | `ci_analysis_demo` 兼容包及原测试保留并持续通过 |

## 7. M3 Jenkins Provider

| ID | 事项 | 状态 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- |
| M3-01 | JenkinsClient | 已完成 | M2-02 | timeout、基础认证、嵌套 Job URL 和稳定错误映射完成 |
| M3-02 | Connection Test | 已完成 | M3-01 | `/api/json` 连接测试返回版本和运行模式 |
| M3-03 | Build/Job 映射 | 已完成 | M3-01 | Freestyle/Pipeline Build 映射统一 Run/Job |
| M3-04 | Console Log | 已完成 | M3-01 | Console 读取、原始长度记录和尾部限长完成 |
| M3-05 | Changeset | 已完成 | M3-01 | 单/多 Changeset 映射统一 CommitChange |
| M3-06 | Jenkins Event | 已完成 | M1、M3-03 | Jenkins Webhook Token、事件映射和失败诊断创建完成 |
| M3-07 | Jenkins Tools | 已完成 | M3-03 至 M3-05 | 通用 Provider Tool 自动按 Jenkins Capability 候选和执行 |
| M3-08 | 兼容矩阵 | 已完成 | M3 | `docs/jenkins_compatibility.md` 记录版本、Job 类型和边界 |
| M3-09 | Jenkins 契约测试 | 已完成 | M3 | Build、Console、Changeset、嵌套路径和事件 Fixture 已覆盖 |
| M3-10 | GitLab/Jenkins 一致性评测 | 已完成 | M2、M3 | 两种 Provider 对失败 Run 输出相同模型和统一状态 |

## 8. M4 知识平台

| ID | 事项 | 状态 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- |
| M4-01 | Knowledge Document Schema | 已完成 | M1 | 来源、版本、ACL 和状态完整 |
| M4-02 | Markdown/JSON 上传 | 已完成 | M4-01 | Pydantic 类型/大小校验与 JSON 结构校验完成 |
| M4-03 | 文档解析和 Chunk | 已完成 | M4-02 | Markdown 标题/代码块和 JSON 结构化切片完成 |
| M4-04 | 敏感信息扫描 | 已完成 | M4-02 | 入库前统一 Secret Mask |
| M4-05 | 去重和版本 | 已完成 | M4-01 | SHA-256 去重、版本递增和 superseded 状态完成 |
| M4-06 | Embedding 后台任务 | 已完成 | M1-05、M4-03 | `knowledge` 队列异步生成确定性本地向量 |
| M4-07 | FAISS 持久化 | 已完成 | M4-06 | 索引写入 Docker 持久卷并通过 `CURRENT` 直接加载 |
| M4-08 | 索引版本和原子切换 | 已完成 | M4-07 | 临时目录构建后以原子替换发布版本和指针 |
| M4-09 | Tenant/Project Filter | 已完成 | M4-01 | 搜索强制 tenant/project/provider ACL |
| M4-10 | 删除和重建索引 | 已完成 | M4-08 | 端到端验证删除后同一标记召回数为 0 |
| M4-11 | 公共知识来源台账 | 已完成 | M4-01 | source URL、license、hash、版本进入数据库和索引元数据 |
| M4-12 | 检索回归评测 | 已完成 | M4-09 | 混合评分、元数据优先级、租户/项目隔离自动测试通过 |

## 9. M5 MVP 验收

| ID | 事项 | 状态 | 依赖 | 完成标准 |
| --- | --- | --- | --- | --- |
| M5-01 | 权限和只读策略检查 | 已完成 | M2 至 M4 | Bearer Key 租户绑定、管理 API 管理员限定、默认 Tool 全只读 |
| M5-02 | Prompt Injection 测试 | 已完成 | M4 | 不可信输入边界和工具策略自动测试通过 |
| M5-03 | Secret 泄漏测试 | 已完成 | M2 至 M4 | Mask 自动测试及容器 E2E 结果未泄漏测试 Secret |
| M5-04 | 故障降级测试 | 已完成 | M1 至 M4 | LLM fallback、RAG 空召回/异常降级、Tool 单项容错已测试 |
| M5-05 | 性能基线 | 已完成 | M1 至 M4 | 容器 20 样本：P50 0.134s、P95 1.191s；资源快照见验收报告 |
| M5-06 | 固定评测集 | 已完成 | M2 至 M4 | GitLab/Jenkins 各 9 类、18 Case，准确率 100% |
| M5-07 | 安装和升级文档 | 已完成 | M1 至 M4 | `platform_operations.md` 覆盖安装、升级、备份和排障 |
| M5-08 | API 和 Webhook 文档 | 已完成 | M2 至 M4 | README、OpenAPI 和 API 示例覆盖新平台接口 |
| M5-09 | 知识文档规范 | 已完成 | M4 | `knowledge_document_format.md` 提供 Markdown/JSON 模板 |
| M5-10 | MVP 验收报告 | 已完成 | 全部 | `mvp_acceptance_report.md` 记录 DoD 和实际证据 |

## 10. 后置事项

| 事项 | 状态 | 目标版本 |
| --- | --- | --- |
| GitHub Actions Provider | 后置 | `0.6.x` |
| PDF/DOCX/HTML 入库 | 后置 | `0.6.x` |
| 模型 Reranker | 后置 | `0.6.x` |
| Web 管理页面 | 后置 | `0.6.x` |
| 自动评论 CI 结果 | 后置 | `0.7.x` |
| 人工审批后重跑 | 后置 | `1.0` 前 |
| Helm 和高可用部署 | 后置 | `1.0` 前 |

## 11. 变更记录

| 日期 | 变更 | 结果 |
| --- | --- | --- |
| 2026-07-24 | 建立产品化开发跟进文档 | 完成当前能力盘点和 MVP 任务拆分 |
| 2026-07-24 | 完成 M0 文档评审和命名确认 | 四份文档评审通过；冻结 `ci_assistant` / `ci-assistant-platform` 命名与 PostgreSQL、Redis、FAISS 持久化方案 |
| 2026-07-25 | 完成 M1-01 Python 项目骨架 | 新增 `pyproject.toml`、`ci_assistant` 包和包元数据测试；现有与新增共 11 项测试通过 |
| 2026-07-25 | 完成 M1-02 配置模型分层 | 新增平台配置模型、四级覆盖加载器、配置模板和生产约束；现有与新增共 16 项测试通过 |
| 2026-07-25 | 完成 M1-03 PostgreSQL 数据层 | 新增 SQLAlchemy/asyncpg 数据库生命周期、事务 Session、模型基类和通用 Repository；现有与新增共 19 项测试通过 |
| 2026-07-25 | 推进 M1-04 至 M1-09 平台骨架 | 完成 Alembic、核心表、Redis/Celery、健康检查、错误 Envelope、诊断持久化 API 和 Docker Compose；28 项测试通过 |
| 2026-07-25 | 完成 M2-01 至 M2-05 Provider 基础迁移 | 新增统一 CI Domain、Protocol、Registry 和独立 GitLabProvider；31 项测试通过 |
| 2026-07-25 | 完成 M2 和 M3 Provider 迁移 | 完成 Provider-aware Tools、Webhook 幂等、通用 Run API、Jenkins 全读链路及跨 Provider 契约；38 项测试通过 |
| 2026-07-25 | 完成 M4 知识平台和诊断接线 | 文档异步入库、版本化 FAISS、ACL 混合检索、真实引用及删除后零召回闭环通过 |
| 2026-07-25 | 完成 M5 容器验收 | 58 项测试、18 Case 固定评测、五服务 Compose、性能/安全/非 root/持久卷验证通过 |

## 12. 下一步

M0–M5 架构迁移已完成。后续进入 `0.6.x` 增强路线；旧
`ci_analysis_demo` 仅作为兼容包保留，新服务入口和默认运行链路均为 `ci_assistant`。

相关文档：

- [产品化可行性分析](ci_assistant_platform_analysis.md)
- [MVP 文档](ci_assistant_platform_mvp.md)
- [开发文档](ci_assistant_platform_development.md)
