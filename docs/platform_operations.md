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

## 排障

- API live 正常、ready 失败：分别检查 PostgreSQL/Redis 网络和凭据。
- Worker 无任务：确认 `diagnosis`、`knowledge` 队列和 Redis broker 一致。
- 文档未激活：检查 `ingestion_jobs.error` 和知识卷写权限。
- Provider 失败：调用连接测试 API，检查最小只读 Token 权限。
- 模型不可用：诊断会输出低置信度 fallback，并在 Trace 记录 `fallback_used`。
