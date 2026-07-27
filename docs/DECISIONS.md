# 工程决策记录

## ADR-001：主包与发行名

- 状态：已接受
- 决策：Python 主包使用 `ci_assistant`，发行名使用 `ci-assistant-platform`。
- 兼容：`ci_analysis_demo` 仅作为旧 API 兼容包。
- 原因：避免新旧模块继续交叉依赖，并保持调用方渐进迁移能力。

## ADR-002：持久化职责拆分

- 状态：已接受
- 决策：PostgreSQL 保存业务和知识元数据，Redis 保存 Celery 队列与短期结果，FAISS
  保存版本化向量索引。
- 原因：知识正文需要事务与审计；队列需要短期、高吞吐状态；向量检索需要独立索引。
- 恢复：PostgreSQL 是业务恢复基线，FAISS 可由知识 Chunk 重建。

## ADR-003：统一 CI Provider

- 状态：已接受
- 决策：诊断编排只依赖 `CIProvider`，GitLab/Jenkins 原始响应限制在 Adapter 内部。
- 原因：统一 Run、Job、Log、Change 和 Webhook 语义，避免业务层绑定单一 CI。

## ADR-004：默认只读和真实引用

- 状态：已接受
- 决策：自动 Tool 默认只读；references 只能来自带 ACL 的真实检索结果。
- 原因：CI 日志和知识均是不可信输入，自动写操作和模型自造引用风险不可接受。

## ADR-005：依赖真源

- 状态：已接受
- 决策：`pyproject.toml` 是项目依赖真源；容器清单和兼容 requirements 由自动测试约束
  名称集合一致。
- 原因：避免本地、容器和兼容安装得到不同的目标运行环境。

## ADR-006：ADOS 渐进治理

- 状态：已接受
- 决策：治理按 P0/P1/P2 渐进实施，不批量重构历史代码；只对实际触及的公共接口补充
  Docstring 和测试。
- 原因：减少治理噪声，保持公开行为和兼容链路稳定。
