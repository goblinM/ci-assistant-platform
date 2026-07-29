# CI Assistant Platform 测试与评测矩阵

## 目标

测试用于保护平台行为，评测用于观察诊断和检索质量。二者必须分开报告：测试通过不代表
外部 Provider 或模型质量已经验证，历史验收结果也不代表当前工作区已经重新回归。

## 自动测试层级

| 层级 | 范围 | 主要证据 | 默认是否需要外部服务 |
| --- | --- | --- | --- |
| 单元测试 | 配置、模型、日志处理、规则网关、工具筛选 | `ci_assistant/tests/test_*.py` | 否 |
| 静态契约测试 | Compose、迁移元数据、依赖同步、Provider Protocol | `test_compose.py`、`test_migrations.py`、`test_provider_contract.py` | 否 |
| 持久化测试 | Repository 事务、诊断状态和事件幂等 | `test_persistence.py`、`test_diagnosis_persistence.py` | 使用测试替身 |
| 知识测试 | Chunk、Secret Mask、FAISS 原子发布和 ACL | `test_knowledge_processing.py`、`test_knowledge_index.py` | 否 |
| 安全与降级 | 租户鉴权、Prompt 边界、RAG/模型失败 | `test_auth.py`、`test_security_controls.py`、`test_orchestrator.py` | 否 |
| Compose E2E | API、Worker、PostgreSQL、Redis、FAISS 实际闭环 | `docs/mvp_acceptance_report.md` 中的验收步骤 | 是 |
| 外部 Provider | 真实 GitLab/Jenkins/GitHub 权限、网络和兼容性 | 部署环境连接测试 | 是 |

默认完整测试：

```bash
pytest
```

按修改范围选择最小回归：

```bash
# 配置和 Compose
pytest -q ci_assistant/tests/test_config.py ci_assistant/tests/test_compose.py

# Worker、失败日志和可靠投递
pytest -q ci_assistant/tests/test_workers.py ci_assistant/tests/test_task_logging.py

# Provider 和只读 Tool
pytest -q \
  ci_assistant/tests/test_provider_contract.py \
  ci_assistant/tests/test_gitlab_provider.py \
  ci_assistant/tests/test_jenkins_provider.py \
  ci_assistant/tests/test_provider_tools.py

# 知识处理与检索
pytest -q \
  ci_assistant/tests/test_knowledge_processing.py \
  ci_assistant/tests/test_knowledge_index.py \
  ci_assistant/tests/test_hybrid_retrieval.py
```

## 固定诊断评测

主平台固定样例位于 `ci_assistant/evaluation_cases.json`，由
`ci_assistant/tests/test_fixed_evaluation.py` 验证。当前集合对 GitLab/Jenkins 各覆盖：

- 依赖缺失
- 依赖冲突
- 测试失败
- 权限或认证失败
- 网络超时
- Runner/Agent 不可用
- Docker 构建失败
- 资源不足
- 未知错误

固定规则基线关注：

- 输出符合 `DiagnosisResult`。
- `error_type` 命中标注。
- 每条结果至少包含一项建议。
- 两种 Provider 使用相同错误类型语义。

## RAG 质量指标

知识检索应按 Provider 和 `error_type` 分组记录：

- Recall@K：期望文档是否进入 Top K。
- MRR：首个正确文档的排序位置。
- Reference hit rate：最终引用是否命中期望来源。
- 空召回率：启用 RAG 时没有任何引用的比例。
- ACL correctness：跨 tenant/project/provider 召回必须为零。

评测样例不能作为知识答案直接导入同一索引，否则会造成数据泄漏。新增知识数据集时，应保留
来源 URL、许可证状态、内容 hash 和数据集版本。

## 离线排序评测

主平台排序样例位于 `ci_assistant/ranking_evaluation_cases.json`。运行：

```bash
make eval-ranking
```

输出 Hybrid 与 Reranker 的 Recall@1、Recall@3、MRR、Metadata hit rate 和
Reference precision，并给出指标增量。该命令使用固定离线结果，不加载真实模型，也不访问
外部服务；用于保护排序指标计算和报告契约，不能替代固定模型、真实知识集上的质量与性能
验收。评测集与生产反馈数据必须版本化、脱敏并避免训练/评测泄漏。

## 用户反馈闭环

诊断反馈通过 `POST /api/v1/diagnoses/{diagnosis_id}/feedback` 按诊断唯一键幂等更新，
支持 helpful、partially_helpful、not_helpful 三档评分、建议采纳状态、纠正后的错误类型和
脱敏评论。单条反馈可按诊断查询；`GET /api/v1/feedback/summary` 提供租户级聚合，供后续
构建匿名离线评测集。反馈不会自动触发模型训练、CI 写操作或知识入库。

## 兼容评测

`make eval` 和 `make eval-rag` 当前仍调用 `ci_analysis_demo` 的旧评测脚本，只用于兼容回归，
不代表主平台测试入口。兼容包退役前，应先把仍需保留的指标迁入 `ci_assistant`，再删除旧
命令。

## 结果记录要求

每次交付只记录实际执行的命令和结果，并明确：

- 是否启动外部服务。
- 是否使用真实 GitLab/Jenkins/GitHub。
- 是否调用外部模型。
- 是否运行完整测试集。
- 失败、跳过和无法验证的项目。
