# CI Assistant 安装、升级与运维

## 安装

1. 复制 `.env.example` 为 `.env`，设置数据库密码、模型、CI Token、Webhook Secret 和
   `API_KEYS_JSON`。
2. 复制 `config.example.yml` 为 `config.yml`，配置 GitLab/Jenkins 连接。
3. 执行 `docker-compose up -d --build`。
4. 检查 `GET /health/ready`，必须同时返回 database/redis 为 `ok`。
5. 使用 `docker-compose logs migrate` 确认 Alembic 到达 head。

`POSTGRES_PASSWORD` 为必填项，Compose 不提供生产默认密码。本地 DBeaver 调试端口默认是
`127.0.0.1:15432`，只允许本机访问；可用 `POSTGRES_PORT` 调整本机端口。已有 PostgreSQL
数据卷不会因为修改环境变量自动更新数据库角色密码，调整密码前应先完成备份和角色变更。

## 升级

1. 备份 PostgreSQL、知识卷和当前镜像版本。
2. 拉取目标版本并审阅迁移说明。
3. 执行 `docker-compose build`。
4. 执行 `docker-compose run --rm migrate alembic upgrade head`。
5. 执行 `docker-compose up -d` 并检查 ready、Worker 和指标。

数据库降级只能在已验证对应 downgrade 且已备份时执行。知识索引可以通过
`POST /api/v1/knowledge/reindex` 重建，不能替代业务数据库备份。

## 备份与恢复

PostgreSQL 是租户、连接、事件、诊断、Trace、知识正文和 Chunk 的业务恢复基线。Redis
只保存队列和短期任务结果，不作为知识数据备份。FAISS 可以从 PostgreSQL 中的有效知识
Chunk 重建，但生产环境仍建议同时备份知识卷以缩短恢复时间。

创建 PostgreSQL 逻辑备份：

```bash
mkdir -p backups
docker-compose exec -T postgres \
  pg_dump -U ci_assistant -d ci_assistant -Fc > backups/ci_assistant.dump
```

备份完成后应记录应用版本、Alembic revision、FAISS `CURRENT` 版本、文件大小和校验和，
并把备份存放到加密且与运行主机隔离的位置。不要提交备份文件到 Git。

恢复演练必须在隔离数据库中进行。基本顺序：

1. 创建与备份兼容的 PostgreSQL 实例。
2. 使用 `pg_restore` 恢复逻辑备份。
3. 确认 Alembic revision 与目标应用兼容。
4. 启动 API/Worker 前执行知识 reindex。
5. 验证租户 ACL、诊断查询、文档数量和抽样引用。
6. 记录恢复时间、数据缺口和回滚方案。

禁止在未备份、未确认目标库的情况下使用带 `--clean` 的恢复命令。生产恢复和角色密码变更
需要单独人工审批。

## 排障

- API live 正常、ready 失败：分别检查 PostgreSQL/Redis 网络和凭据。
- Worker 无任务：确认 `diagnosis`、`knowledge` 队列和 Redis broker 一致。
- 文档未激活：检查 `ingestion_jobs.error` 和知识卷写权限。
- Provider 失败：调用连接测试 API，检查最小只读 Token 权限。
- 模型不可用：诊断会输出低置信度 fallback，并在 Trace 记录 `fallback_used`。
