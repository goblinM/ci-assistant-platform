# CI Assistant Platform 0.5.0 MVP 验收报告

> 验收日期：2026-07-25  
> 结论：M0–M5 目标架构迁移通过

## 验证结果

- `venv/bin/pytest -q`：58 项通过。
- `compileall` 与 `git diff --check`：通过。
- Alembic 在 PostgreSQL 16 执行到 head。
- Docker Compose 实际启动 API、Worker、Migration、PostgreSQL、Redis。
- `/health/ready`：database/redis 均为 `ok`；`/metrics` 可抓取。
- Worker 注册 diagnosis/knowledge 三类任务，并以 uid/gid 999 非 root 运行。
- 手动日志闭环：API 接收、Redis 派发、Worker 诊断、PostgreSQL 持久化成功，
  `ModuleNotFoundError` 识别为 `dependency_missing`，测试 Secret 未泄漏。
- 知识闭环：Markdown 上传后异步激活，诊断返回真实知识引用；逻辑删除并重建
  索引后相同标记召回数为 0；FAISS `CURRENT` 位于持久卷。
- 固定评测：GitLab/Jenkins 各覆盖 9 类错误，共 18 Case，规则基线准确率 100%。

## 性能和资源基线

容器环境、规则诊断网关、5 并发、20 个端到端样本：

| 指标 | 结果 |
| --- | --- |
| 成功率 | 20/20 |
| P50 | 0.134 秒 |
| P95 | 1.191 秒 |
| 最大值 | 1.194 秒 |

空闲后一次资源快照：

| 服务 | CPU | 内存 |
| --- | ---: | ---: |
| API | 0.77% | 78.2 MiB |
| Worker | 4.43% | 355.8 MiB |
| PostgreSQL | 6.56% | 40.95 MiB |
| Redis | 2.97% | 8.777 MiB |

该基线用于本地 MVP 回归，不替代客户环境的容量测试。

## DoD 审核

- 一条 Compose 命令启动、配置校验、健康检查：通过。
- GitLab/Jenkins 统一 Provider、连接测试能力、Webhook 和契约：通过自动契约测试；
  真实外部实例凭据属于部署配置，不纳入仓库验收。
- 手动日志、统一 Run 诊断、结果/reference/trace 持久化：通过。
- Markdown/JSON 上传、版本、索引、ACL 检索和删除：通过。
- 默认只读工具、参数校验、Prompt Injection 与 Secret 防护：通过。
- 单元/集成/固定评测、运维/API/知识文档和来源许可证字段：通过。

兼容包 `ci_analysis_demo` 继续保留以避免旧调用方立即中断；生产入口、容器入口、数据、
任务、Provider 和知识链路已全部迁移至 `ci_assistant`。
