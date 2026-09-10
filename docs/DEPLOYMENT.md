# CI Assistant Platform 本地 Docker 部署与升级

本文面向使用仓库根目录 `docker-compose.yml` 在本机部署或更新镜像的场景。当前 Compose
包含 `api`、`worker`、`migrate`、`postgres` 和 `redis` 五个服务；PostgreSQL、Redis 和知识
索引分别使用持久化卷。升级应用镜像时不得删除这些数据卷。

## 1. 部署边界

- API 对外端口默认为 `8080`，可通过 `.env` 中的 `APP_PORT` 调整。
- PostgreSQL 只映射到本机 `127.0.0.1:15432`，可通过 `POSTGRES_PORT` 调整。
- `migrate` 在 API 和 Worker 启动前执行 `alembic upgrade head`。
- API 和 Worker 从同一份源码构建，并共享 `knowledge-data` 卷。
- Redis 只承载队列和短期结果；PostgreSQL 是业务数据真源。
- Agent 默认关闭。启用 Agent 仍需请求显式传递 `mode=agent`。
- P1B 是只提案模式：批准提案不会评论、修改代码或重跑 CI。

以下命令均在项目根目录执行：

```bash
cd /Users/amo/Documents/Coding/AI/ci-assistant-platform
```

## 2. 首次部署

### 2.1 准备配置

首次部署时复制模板：

```bash
cp .env.example .env
cp config.example.yml config.yml
```

至少修改 `.env` 中的：

```text
POSTGRES_PASSWORD=本地强密码
APP_PORT=8080
API_KEYS_JSON={}
```

如使用 OpenAI-compatible 模型，再设置：

```text
LLM_API_URL=https://模型服务地址/v1
LLM_API_KEY=模型服务密钥
LLM_MODEL=模型名称
WORKER_AI_PROVIDER=openai_compatible
```

仅做本地确定性规则测试时，可保持：

```text
WORKER_AI_PROVIDER=rule
```

启用只读 Agent P0/P1A/P1B：

```text
CI_ASSISTANT__AGENT__ENABLED=true
CI_ASSISTANT__AGENT__MAX_ROUNDS=3
CI_ASSISTANT__AGENT__MAX_TOOL_CALLS=4
CI_ASSISTANT__AGENT__TIMEOUT_SECONDS=45
```

不要把 `.env`、Token、Webhook Secret 或真实客户日志提交到 Git。已有 `.env` 时不要重新
复制模板覆盖它，应手工对照 `.env.example` 增补新配置。

### 2.2 校验 Compose 配置

```bash
docker-compose config -q
```

命令无输出且退出码为 `0` 表示配置可解析。不要把完整 `docker-compose config` 输出粘贴到
工单或聊天中，因为展开后的配置可能包含 Secret。

### 2.3 构建并启动

```bash
docker-compose build --pull
docker-compose run --rm migrate
docker-compose up -d --no-build
```

`migrate` 会先等待 PostgreSQL 健康，再升级到当前 Alembic head。`up` 阶段可能再次幂等检查
迁移，这是正常行为。

### 2.4 检查状态

```bash
docker-compose ps
docker-compose logs --tail=100 migrate
docker-compose logs --tail=100 api
docker-compose logs --tail=100 worker
curl --fail http://127.0.0.1:8080/health/ready
```

验收标准：

- `postgres`、`redis`、`api`、`worker` 正常运行。
- `migrate` 退出码为 `0`。
- `/health/ready` 返回 HTTP `200`，database 和 redis 均为 `ok`。
- Worker 日志没有持续数据库连接、Redis Broker 或模型初始化错误。

## 3. 从旧镜像升级到当前版本

本次版本包含 Agent P1A/P1B、可靠性和证据缺口回放迁移，目标 Alembic revision 为
`20260824_0007`。升级前必须
备份 PostgreSQL；知识卷建议同时备份或至少记录当前 FAISS `CURRENT` 版本。

### 3.1 升级前检查

确认当前容器和工作区：

```bash
docker-compose ps
docker-compose images
git status --short
git rev-parse --short HEAD
```

如工作区存在未提交修改，先确认这些修改属于本次目标版本。不要通过 `git reset --hard` 或
删除目录来清理工作区。

检查当前数据库 revision：

```bash
docker-compose exec -T postgres \
  psql -U ci_assistant -d ci_assistant \
  -c 'SELECT version_num FROM alembic_version;'
```

### 3.2 备份 PostgreSQL

```bash
mkdir -p backups
docker-compose exec -T postgres \
  pg_dump -U ci_assistant -d ci_assistant -Fc \
  > backups/ci_assistant-before-agent-p1.dump
```

检查备份文件不是空文件：

```bash
ls -lh backups/ci_assistant-before-agent-p1.dump
shasum -a 256 backups/ci_assistant-before-agent-p1.dump
```

备份文件包含业务数据和潜在敏感信息，不得提交到 Git。重要环境应把备份复制到加密且与
运行主机隔离的位置。

### 3.3 构建新镜像

先校验配置，再构建：

```bash
docker-compose config -q
docker-compose build --pull
docker-compose images
```

如只修改了应用源码而不希望刷新基础镜像，可省略 `--pull`：

```bash
docker-compose build
```

不要在确认新镜像可用前执行镜像清理，旧镜像是应用层快速回滚依据。

### 3.4 执行数据库迁移

```bash
docker-compose run --rm migrate
```

迁移成功后确认 revision：

```bash
docker-compose exec -T postgres \
  psql -U ci_assistant -d ci_assistant \
  -c 'SELECT version_num FROM alembic_version;'
```

预期：

```text
20260824_0007
```

确认 P1 表存在：

```bash
docker-compose exec -T postgres \
  psql -U ci_assistant -d ci_assistant \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('agent_runs','agent_steps','action_proposals','action_proposal_audits') ORDER BY tablename;"
```

### 3.5 更新 API 和 Worker

```bash
docker-compose up -d --no-build --force-recreate api worker
docker-compose ps
```

PostgreSQL、Redis 和数据卷不需要重建。禁止执行：

```text
docker-compose down -v
```

该命令会删除 Compose 管理的 PostgreSQL、Redis 和知识持久化卷。

### 3.6 升级后验证

健康检查：

```bash
curl --fail http://127.0.0.1:8080/health/ready
curl --fail http://127.0.0.1:8080/metrics
```

查看近期日志：

```bash
docker-compose logs --tail=200 api
docker-compose logs --tail=200 worker
docker-compose logs --tail=100 migrate
```

提交一条无敏感信息的规则诊断：

```bash
curl -sS -X POST http://127.0.0.1:8080/api/v1/diagnoses/logs \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "log_text": "ModuleNotFoundError: No module named requests",
    "use_rag": false,
    "use_tools": false,
    "mode": "agent"
  }'
```

配置了 API Key 时增加：

```text
-H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}"
```

接口应返回 HTTP `202`。使用响应中的 `diagnosis_id` 查询结果：

```bash
curl -sS \
  http://127.0.0.1:8080/api/v1/diagnoses/DIAGNOSIS_ID
```

最终状态应为 `succeeded`。启用了 Agent 且请求使用 `mode=agent` 时，数据库应出现对应
`agent_runs`；规则网关通常直接返回最终诊断，因此可能只有 `final_answer` Step。

检查 P1 数据：

```bash
docker-compose exec -T postgres \
  psql -U ci_assistant -d ci_assistant \
  -c 'SELECT id, diagnosis_id, status, rounds, tool_calls, stop_reason FROM agent_runs ORDER BY created_at DESC LIMIT 5;'
```

P1B 的动作提案即使被批准，也只更新 `action_proposals` 并写入
`action_proposal_audits`，不会调用外部 CI 或代码仓库。

## 4. 常用维护命令

查看服务：

```bash
docker-compose ps
docker-compose top
```

持续查看日志：

```bash
docker-compose logs -f api worker
```

只重启应用，不重建镜像：

```bash
docker-compose restart api worker
```

代码变化后重建应用镜像：

```bash
docker-compose build api worker migrate
docker-compose run --rm migrate
docker-compose up -d --no-build --force-recreate api worker
```

安全停止服务但保留数据卷：

```bash
docker-compose down
```

重新启动：

```bash
docker-compose up -d
```

## 5. 回滚

### 5.1 仅回滚应用镜像

如果新版本 API 或 Worker 异常，但迁移已经成功，可先回滚应用源码/镜像。P1A/P1B 迁移仅
新增表，旧应用不会主动使用这些表；在确认兼容后可保留数据库 revision，不必立即执行
downgrade。

回滚前记录当前 `docker-compose images` 输出，并确认旧镜像 ID 仍存在。恢复到已验证的旧
代码版本后执行：

```bash
docker-compose build
docker-compose up -d --no-build --force-recreate api worker
curl --fail http://127.0.0.1:8080/health/ready
```

### 5.2 数据库回滚

默认不要执行 Alembic downgrade。只有同时满足以下条件时才能评估数据库回滚：

1. 已停止 API 和 Worker 写入。
2. 已验证备份可以恢复。
3. 已确认目标 revision 和 downgrade 脚本。
4. 已评估 `agent_runs`、`agent_steps`、提案与审批审计数据的丢失风险。

如果迁移失败且事务已自动回滚，应先检查 `migrate` 日志，不要重复修改数据库表。需要恢复
备份时，应在隔离数据库先完成恢复演练，禁止直接对当前数据卷使用带 `--clean` 的恢复命令。

## 6. 常见问题

### Compose 提示必须设置 POSTGRES_PASSWORD

确认项目根目录存在 `.env`，且 `POSTGRES_PASSWORD` 不是空值。修改 `.env` 不会自动修改
已有 PostgreSQL 数据卷中的角色密码；已有数据卷的密码变更需单独执行数据库角色变更。

### migrate 成功但 API 无法启动

依次检查：

```bash
docker-compose logs --tail=200 migrate
docker-compose logs --tail=200 postgres
docker-compose logs --tail=200 redis
docker-compose logs --tail=200 api
```

重点确认数据库 URL、Redis URL、数据卷权限和 `.env` 配置。

### Agent 请求仍走 Workflow

必须同时满足：

- `.env` 设置 `CI_ASSISTANT__AGENT__ENABLED=true`。
- 请求 Body 设置 `"mode": "agent"`。
- 更新配置后重新创建 API 和 Worker 容器。

```bash
docker-compose up -d --force-recreate api worker
```

### Worker 没有消费任务

```bash
docker-compose logs --tail=200 worker
docker-compose exec redis redis-cli ping
```

预期 Redis 返回 `PONG`。同时确认 Worker 监听 `diagnosis,knowledge` 队列，API 与 Worker 的
`REDIS_URL` 指向同一个 Redis 服务。

### 更新后数据库中没有 P1 表

检查 revision 和迁移日志：

```bash
docker-compose logs migrate
docker-compose exec -T postgres \
  psql -U ci_assistant -d ci_assistant \
  -c 'SELECT version_num FROM alembic_version;'
```

revision 不是 `20260824_0007` 时，确认新镜像同时包含 P1 migration、可靠性 migration 和
`ci_assistant/persistence/migrations/versions/20260824_0007_agent_evidence_gap.py`，然后重新执行
`docker-compose run --rm migrate`。
