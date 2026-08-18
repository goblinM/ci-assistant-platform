# 治理与产品待办

本文件是当前优先级和后续事项的唯一维护入口。已完成变化记录在 `CHANGELOG.md`，历史
MVP 验收证据保留在 `mvp_acceptance_report.md`。

## 当前

- 保持 GitHub Actions 测试、编译和 Alembic 离线校验稳定。
- 外部 GitLab/Jenkins/GitHub 凭据可用时补充真实连接验收记录。
- 建立定期 PostgreSQL 备份和恢复演练记录。

## 后续

- P1C：在 P0/P1A 指标证明收益后，设计审核式 Episodic Memory、版本化 Skill 和只读 MCP
  Adapter；不得沿用提案审批作为 Memory 或工具永久授权。
- P2：仅在单 Agent 指标证明存在瓶颈后，评估按需 Critic、模型路由和隔离子 Agent。
- 将仍有价值的旧评测指标迁入 `ci_assistant`。
- 在满足架构文档中的五项门槛后，单独评审兼容包退役。
- 评估依赖锁定、SBOM、镜像扫描和依赖漏洞检查。
- 使用固定真实模型与脱敏知识集补充 Reranker 质量、延迟和资源基线。

## 已完成

- 2026-08-12 完成 Agent P1A/P1B 只提案模式：Run/Step 检查点、Worker 续跑、租户级只读
  Replay、Tool allow/ask/deny 元数据、Action Proposal 与不可变审批审计；未增加动作执行器。
- 2026-08-10 完成默认关闭的只读 Agent P0：有界 Loop、双重开关、运行状态、硬预算、
  脱敏轨迹、稳定回退和 Workflow/Agent 对照评测契约。
- 2026-07-28 完成公共函数中文 Docstring 专项治理；ADOS 静态扫描缺口归零。
- 2026-07-28 完成只读 GitHub Actions Provider 和统一 Provider 契约接入。
- 2026-07-28 完成 HTML/DOCX 原生解析和 Unlimited-OCR PDF 接入。
- 2026-07-29 完成可配置、可降级的 Cross-Encoder/BGE Reranker 接入。
- 2026-07-29 完成离线排序评测、诊断反馈闭环和本地 embedding cache。

## 暂不执行

- 不为追求文件规模指标立即拆分兼容层大文件。
- 不自动评论、修改代码或重跑 CI。
- 不在缺少 Agent 轨迹评测、预算和审批状态机时引入 Multi-Agent 或开放写工具。
- 不在没有容量与运维需求时引入 Kubernetes。
