# CI Assistant Platform 快速接手

本文用于帮助新开发者或自动化协作者快速建立项目上下文。项目的完整产品与设计材料继续
保留在原文档中；本文只提供真实入口、核心链路、修改导航和验证顺序。

## 1. 项目用途与当前边界

CI Assistant Platform 是可私有化部署的 CI 失败诊断平台，当前统一接入 GitLab、Jenkins
和 GitHub Actions，并通过 PostgreSQL、Redis/Celery、FAISS 以及规则或
OpenAI-compatible 网关生成结构化诊断。

- 主运行包：`ci_assistant`
- 兼容包：`ci_analysis_demo`，只维护旧 API 兼容性
- 当前版本：以 `pyproject.toml` 中的版本为准
- 默认行为：分析和建议，不自动修改代码、通知外部系统或重跑 CI
- 公开兼容边界：API、Alembic 迁移历史、`CIProvider` Protocol、知识索引格式

开始修改前依次阅读：

1. 根目录 `AGENTS.md`
2. `README.md`
3. `docs/architecture.md`
4. `docs/DEVELOPMENT.md`
5. `docs/TODO.md`
6. 与任务相关的安全、运维或专项设计文档

## 2. 运行入口

| 场景 | 真实入口 |
| --- | --- |
| FastAPI 应用 | `ci_assistant.main:app` |
| CLI 命令 | `ci-assistant` → `ci_assistant.main:main` |
| 本地开发服务 | `venv/bin/uvicorn ci_assistant.main:app --reload --port 8080` |
| Celery Worker | `ci_assistant.workers.celery_app:app` |
| 诊断任务 | `ci_assistant.workers.diagnosis_tasks` |
| 知识任务 | `ci_assistant.workers.ingestion_tasks` |
| 数据库迁移 | `alembic.ini`、`ci_assistant/persistence/migrations/` |
| 容器编排 | `docker-compose.yml` |
| 本地 Docker 部署与升级 | `docs/DEPLOYMENT.md` |
| API 文档 | `http://127.0.0.1:8080/docs` |
| 就绪检查 | `GET /health/ready` |

应用启动时会加载配置、建立 PostgreSQL/Redis 生命周期、同步配置中的 CI Connection，
初始化 Provider Manager、文档解析器和 Celery Dispatcher。容器启动顺序由 Compose 保证：
PostgreSQL → Alembic migrate → API/Worker；Redis 健康后 API/Worker 才启动。

## 3. 核心链路

### Manual 诊断

```text
POST /api/v1/diagnoses/logs 或 /runs
→ Tenant 鉴权
→ diagnoses 写入 queued
→ Redis/Celery diagnosis 队列
→ Diagnosis Worker
→ Mode Router（默认 Workflow；双重开关可选 bounded read-only Agent）
→ 日志预处理、Provider 只读上下文、RAG
→ 规则或 OpenAI-compatible Gateway
→ DiagnosisResult 校验
→ diagnoses / analysis_traces 更新
```

日志直传使用 `/logs`；已有 CI Run 使用 `/runs`，由 Provider 获取 Run、Job 和日志。
结果通过 `GET /api/v1/diagnoses/{diagnosis_id}` 查询。

Agent P0 只有请求 `mode=agent` 且 `agent.enabled=true` 时启用；否则仍走 Workflow。Agent
停止或异常也回退 Workflow，不支持任何写工具。

诊断完成后可向 `POST /api/v1/diagnoses/{diagnosis_id}/feedback` 提交脱敏反馈；反馈按诊断
幂等更新并保持租户隔离，聚合结果由 `GET /api/v1/feedback/summary` 提供。

### Webhook 诊断

```text
GitLab / Jenkins / GitHub Webhook
→ webhook_deliveries 独立事务记录 received
→ Provider 验签
→ 解析并规范化 CIEvent
→ ci_events 幂等落库
→ webhook_deliveries 更新 processed / duplicate / rejected / failed
→ 满足诊断策略时创建 diagnoses
→ Celery 诊断链路
```

`webhook_deliveries` 记录每次 HTTP 投递的 Payload Hash、签名结果、处理状态和稳定错误码，
不保存原始 Body 或认证 Header。`ci_events` 保存验签和解析成功后的业务事件，并通过
Provider、Connection 和外部事件 ID 保证幂等。

GitLab pending Pipeline 会匹配作业标签与项目在线 Runner；只有确认不存在兼容 Runner
时才创建 `runner_unavailable` 诊断，正常排队不视为故障。

### 知识入库与检索

```text
Knowledge API
→ Markdown/JSON/HTML/DOCX 受限解析，或 PDF → Unlimited-OCR
→ Secret Mask、Chunk
→ PostgreSQL Document / Chunk / IngestionJob
→ Redis/Celery knowledge 队列
→ Embedding 本地 SQLite cache（失败时直接计算）
→ 版本化 FAISS 构建与 CURRENT 原子切换
→ tenant / project / provider ACL 混合检索
→ 可选 Cross-Encoder/BGE Reranker
```

PostgreSQL 是知识正文和元数据的恢复基线；FAISS 可由有效 Chunk 重建。

## 4. 目录与修改导航

| 修改目标 | 首选位置 | 必要关注 |
| --- | --- | --- |
| API、鉴权、错误响应 | `ci_assistant/api/` | 公开 API 和租户边界 |
| 配置与 Secret 加载 | `ci_assistant/core/config.py` | 覆盖顺序和生产校验 |
| 诊断编排 | `ci_assistant/diagnosis/` | 降级、日志脱敏和结果 Schema |
| GitLab/Jenkins/GitHub | `ci_assistant/providers/` | Provider Protocol 和只读能力 |
| Provider 工具 | `ci_assistant/tools/` | 默认只读、项目允许列表 |
| 数据模型与 Repository | `ci_assistant/persistence/` | 事务边界和追加式迁移 |
| Worker | `ci_assistant/workers/` | 队列、重试、幂等和安全日志 |
| 文档解析、检索、FAISS | `ci_assistant/knowledge/` | 文件限制、ACL 和索引兼容 |
| 结果模型 | `ci_assistant/schemas/` | 下游兼容性 |
| 新平台测试 | `ci_assistant/tests/` | 实际修改模块专项回归 |
| 旧接口兼容修复 | `ci_analysis_demo/` | 不继续扩展新架构 |

数据库结构变化必须新增
`ci_assistant/persistence/migrations/versions/` 下的 Alembic revision，不得修改已经应用的
历史迁移。依赖以 `pyproject.toml` 为真源；容器依赖同步到
`requirements-runtime.txt`。

## 5. 配置与本地数据

配置覆盖顺序：

```text
代码默认值 < config.yml < 环境变量 < Secret 文件
```

- 从 `.env.example` 和 `config.example.yml` 创建本地配置。
- `.env`、Token、Webhook Secret 和客户 CI 日志不得读取、提交或输出。
- Compose PostgreSQL 默认地址为 `127.0.0.1:15432/ci_assistant`。
- Redis 仅作为队列和短期结果存储；业务审计数据在 PostgreSQL。
- FAISS 位于知识持久卷；恢复和重建步骤见 `docs/platform_operations.md`。

## 6. 最小开发与验证

建立环境：

```bash
python -m venv venv
venv/bin/pip install -e ".[dev]"
```

默认验证：

```bash
venv/bin/pytest -q
venv/bin/python -m compileall -q ci_assistant ci_analysis_demo
git diff --check
```

数据库迁移静态验证：

```bash
venv/bin/alembic upgrade head --sql
```

需要真实服务时，先确认 `.env` 已设置 `POSTGRES_PASSWORD`，再执行：

```bash
docker-compose up -d --build
docker-compose ps
curl http://127.0.0.1:8080/health/ready
```

只运行与修改范围相称的命令；不得为验证文档执行不可信脚本、安装未授权依赖、调用外部
Provider 或触发 CI 写操作。

## 7. 接手一个任务的检查清单

1. 确认任务属于主包、兼容修复、文档、迁移或运维中的哪一类。
2. 检查工作区已有修改，避免覆盖其他人的未提交内容。
3. 阅读对应模块、现有测试、`docs/DECISIONS.md` 和相关专项文档。
4. 冻结公开 API、Provider Protocol、迁移历史和索引兼容边界。
5. 采用最小修改；新增或实际修改的公共 Python 函数、类补充准确中文 Docstring。
6. 行为、配置、命令或架构变化同步更新现有文档。
7. 运行专项测试、完整回归、源码编译和 `git diff --check`，如实记录未执行项。

当前优先级只在 `docs/TODO.md` 维护；架构决策见 `docs/DECISIONS.md`；排障记录入口见
`docs/DEBUG.md`；版本变化见
`docs/CHANGELOG.md`。
