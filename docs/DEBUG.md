# 排障记录入口

具体安装与运行排障见 `platform_operations.md`。新增缺陷记录至少包含：现象、影响范围、
根因、修复、验证命令和未验证项，禁止粘贴真实 Secret 或完整客户 CI 日志。

## API live 正常但 ready 失败

- 检查 PostgreSQL 与 Redis 的网络和凭据。
- 确认迁移服务已成功到达 Alembic head。
- 使用 `/health/ready` 的分项结果定位依赖，不在日志中打印连接密码。

## Worker 没有处理任务

- 确认 API 和 Worker 使用相同 Redis URL。
- 检查 `diagnosis`、`knowledge` 队列是否注册。
- 检查 Worker 安全失败字段：`task_name`、`task_identifier`、`error_code`、
  `exception_type`。

## 知识文档未激活或无引用

- 查询 `ingestion_jobs.status/error`，但不要输出知识全文。
- 确认知识卷可写且租户目录存在 `CURRENT`。
- 检查 tenant/project/provider ACL；删除后的文档不应再次召回。
- FAISS 损坏或丢失时，通过知识 reindex API 重建。

## Provider 或模型失败

- 使用管理员连接测试 API 区分鉴权、资源不存在和上游不可用。
- 模型不可用应进入低置信度 fallback；RAG 或单个 Tool 失败不应终止整个进程。
- 记录异常类型和稳定错误码，不记录上游响应正文。

## 本地 PostgreSQL 无法连接

- DBeaver 默认连接 `127.0.0.1:15432/ci_assistant`。
- Compose 重建前确认 `.env` 已设置 `POSTGRES_PASSWORD`。
- 已有数据卷不会因环境变量变化自动修改数据库角色密码。
