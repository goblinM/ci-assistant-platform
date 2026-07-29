# 治理与产品待办

本文件只维护当前优先级入口；完整产品里程碑保留在
`ci_assistant_platform_tracker.md`。

## 当前

- 保持 GitHub Actions 测试、编译和 Alembic 离线校验稳定。
- 外部 GitLab/Jenkins/GitHub 凭据可用时补充真实连接验收记录。
- 建立定期 PostgreSQL 备份和恢复演练记录。

## 后续

- 将仍有价值的旧评测指标迁入 `ci_assistant`。
- 在满足架构文档中的五项门槛后，单独评审兼容包退役。
- 评估依赖锁定、SBOM、镜像扫描和依赖漏洞检查。
- 使用固定真实模型与脱敏知识集补充 Reranker 质量、延迟和资源基线。

## 已完成

- 2026-07-28 完成公共函数中文 Docstring 专项治理；ADOS 静态扫描缺口归零。
- 2026-07-28 完成只读 GitHub Actions Provider 和统一 Provider 契约接入。
- 2026-07-28 完成 HTML/DOCX 原生解析和 Unlimited-OCR PDF 接入。
- 2026-07-29 完成可配置、可降级的 Cross-Encoder/BGE Reranker 接入。
- 2026-07-29 完成离线排序评测、诊断反馈闭环和本地 embedding cache。

## 暂不执行

- 不为追求文件规模指标立即拆分兼容层大文件。
- 不自动评论、修改代码或重跑 CI。
- 不在没有容量与运维需求时引入 Kubernetes。
