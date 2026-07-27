# 治理与产品待办

本文件只维护当前优先级入口；完整产品里程碑保留在
`ci_assistant_platform_tracker.md`。

## 当前

- 保持 GitHub Actions 测试、编译和 Alembic 离线校验稳定。
- 后续实际修改公共函数时渐进补充中文 Docstring。
- 外部 GitLab/Jenkins 凭据可用时补充真实连接验收记录。
- 建立定期 PostgreSQL 备份和恢复演练记录。

## 后续

- 将仍有价值的旧评测指标迁入 `ci_assistant`。
- 在满足架构文档中的五项门槛后，单独评审兼容包退役。
- 评估依赖锁定、SBOM、镜像扫描和依赖漏洞检查。
- 评估 GitHub Actions Provider、更多知识格式和反馈闭环。

## 暂不执行

- 不批量补历史 Docstring。
- 不为追求文件规模指标立即拆分兼容层大文件。
- 不自动评论、修改代码或重跑 CI。
- 不在没有容量与运维需求时引入 Kubernetes。
