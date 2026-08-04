# 开发入口

本文件是 ADOS 开发索引。当前组件与边界见 `architecture.md`，已接受的设计取舍见
`DECISIONS.md`，测试分层见 `evaluation.md`。

## 环境

```bash
python -m venv venv
venv/bin/pip install -e ".[dev]"
```

依赖以根目录 `pyproject.toml` 为真源。容器运行依赖同步到
`requirements-runtime.txt`；`requirements.txt` 仅为兼容安装入口。

## 常用命令

```bash
venv/bin/pytest -q
venv/bin/python -m compileall -q ci_assistant ci_analysis_demo
venv/bin/alembic upgrade head --sql
git diff --check
```

本地运行：

```bash
venv/bin/uvicorn ci_assistant.main:app --reload --port 8080
```

Compose 运行前必须在 `.env` 中设置 `POSTGRES_PASSWORD`：

```bash
docker-compose up -d --build
docker-compose ps
```

## 修改规则

- 新功能进入 `ci_assistant`；`ci_analysis_demo` 只修复兼容问题。
- 数据库变更新增 Alembic revision，不改写既有迁移。
- 修改 Provider、Worker、知识索引或安全边界时，运行对应专项测试和完整回归。
- 不在日志、测试 Fixture 或文档中提交真实 Token、Prompt、CI 日志和客户数据。
- 公开 API、Provider Protocol 和索引格式变化必须单独评审。

## 关联文档

- 架构：`architecture.md`
- API：`api_examples.md`
- 运维：`platform_operations.md`
- 安全：`security_verification.md`
- 当前任务：`TODO.md`
- 决策：`DECISIONS.md`
