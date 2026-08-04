# Changelog

本项目使用增量记录，不回写或重排历史迁移。

## Unreleased

- 收敛现行工程文档入口，移除已完成迁移阶段的重复分析、开发、跟进和产品化设计文档。
- 增加 Webhook 全投递脱敏审计和 GitLab 无匹配 Runner 诊断。
- 新增 ADOS `PROJECT_ONBOARDING.md` 快速接手入口。
- 建立 GitHub Actions 测试、编译和 Alembic 离线迁移质量门。
- 补齐 ADOS 开发、待办、决策、排障和变更记录入口。
- 补充 PostgreSQL/FAISS 备份恢复和治理说明。
- 完成 256 处公共函数中文 Docstring 专项治理，静态扫描缺口归零。

## 0.6.2 — 2026-07-29

- 增加主平台离线排序评测及 Hybrid/Reranker 指标对比。
- 增加租户隔离的诊断反馈写入、查询和聚合 API。
- 增加不保存原文、故障可降级的本地 SQLite embedding cache。
- 增加 `disabled | local | http` Cross-Encoder/BGE Reranker 后端，默认关闭。
- 本地后端使用可选 SentenceTransformers 依赖，按 Worker 进程懒加载并缓存模型。
- Hybrid Search 在启用 Reranker 时扩大候选集，重排后保留原 `hybrid_score`。
- Reranker 网络、超时、HTTP 和响应契约异常自动降级到原 Hybrid 排序。
- 默认平台镜像不增加 SentenceTransformers、Torch、CUDA 或模型权重。

## 0.6.1 — 2026-07-28

- 增加 PDF、DOCX、HTML 文件知识上传端点。
- DOCX/HTML 使用受限原生解析，PDF 使用独立 Unlimited-OCR 服务。
- 增加文件大小、DOCX ZIP Bomb、PDF 页数和总像素安全限制。
- 解析文本复用 Secret Mask、Chunk、PostgreSQL、FAISS 和 Provider ACL。

## 0.6.0 — 2026-07-28

- 增加只读 GitHub Actions Provider，覆盖 Workflow Run、Job、日志、Head Commit 和
  `workflow_run`/`workflow_job` Webhook。
- GitHub Webhook 使用 HMAC-SHA256 验签，连接支持 GitHub App Installation Token。
- GitLab、Jenkins 和 GitHub Actions 继续共享统一 Provider 契约与只读 Tool。

## 0.5.0 — 2026-07-25

- 完成 `ci_assistant` 主平台包和 `ci-analysis-platform` 发行配置。
- 建立 PostgreSQL、Redis/Celery、Alembic 和 Docker Compose 五服务。
- 提供 GitLab/Jenkins 统一 Provider、Webhook 和只读 Tool。
- 提供 Markdown/JSON 知识入库、ACL 混合检索和版本化 FAISS。
- 提供租户鉴权、Secret Mask、结构化诊断、指标和固定评测。
- 保留 `ci_analysis_demo` 作为旧 API 兼容包。

## ADOS 治理 — 2026-07-27

- P0：建立 Git 基线、项目级 `AGENTS.md`、真实架构文档和数据库本机安全边界。
- P1：统一 Worker 安全失败日志、依赖真源、测试矩阵和兼容包退役条件。
