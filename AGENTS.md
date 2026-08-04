# CI Assistant Platform 协作约束

本项目遵循 ADOS 工程标准。修改前先阅读本文件及下列真实项目文档：

- 项目用途、安装和常用命令：`README.md`
- 快速接手顺序、真实入口和修改导航：`docs/PROJECT_ONBOARDING.md`
- 当前架构和兼容边界：`docs/architecture.md`
- 开发环境和验证命令：`docs/DEVELOPMENT.md`
- 开发设计与迁移原则：`docs/architecture.md`、`docs/DECISIONS.md`
- 当前治理与产品待办：`docs/TODO.md`
- 已接受工程决策：`docs/DECISIONS.md`
- 排障与变更记录：`docs/DEBUG.md`、`docs/CHANGELOG.md`
- 当前优先级与后续事项：`docs/TODO.md`
- 安全要求：`docs/security_verification.md`

## 项目边界

- `ci_assistant` 是主运行包；新功能默认只能进入该包。
- `ci_analysis_demo` 是旧 API 兼容包。除兼容缺陷修复外，不得继续扩展其架构。
- 保持公开 API、数据库迁移历史、Provider Protocol 和知识索引格式向后兼容。
- 不移动现有目录，不做与当前任务无关的批量重构。
- 默认工具只读；写操作、外部通知和 CI 重跑必须单独获得授权。
- 不读取、提交或输出 `.env`、Token、Webhook Secret、CI 日志中的敏感信息。

## 开发要求

- 优先可读性和最小修改，避免为单一调用提前抽象。
- 工具函数按领域放入对应模块，不新增无边界的通用工具箱。
- 新增或实际修改的公共 Python 函数、类应补充准确的中文 Docstring。
- 行为、配置、命令或架构发生变化时，同步更新现有对应文档。
- 数据库结构变化必须新增 Alembic revision，不改写已应用的迁移。
- 依赖以 `pyproject.toml` 为项目真源；容器运行依赖同步到
  `requirements-runtime.txt`。

## 验证要求

- 默认测试命令：`pytest`。
- 最小回归应覆盖实际修改模块；影响配置、迁移、Provider、Worker 或知识索引时，
  增加相应专项测试。
- 交付前检查 `git diff --check`，并如实报告未执行或无法执行的验证。
- 不执行不可信脚本，不安装依赖或启动外部服务，除非当前任务明确授权。
