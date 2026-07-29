# CI Assistant 安装、升级与运维

## 安装

1. 复制 `.env.example` 为 `.env`，设置数据库密码、模型、CI Token、Webhook Secret 和
   `API_KEYS_JSON`。
2. 复制 `config.example.yml` 为 `config.yml`，配置 GitLab/Jenkins/GitHub 连接。
3. 执行 `docker-compose up -d --build`。
4. 检查 `GET /health/ready`，必须同时返回 database/redis 为 `ok`。
5. 使用 `docker-compose logs migrate` 确认 Alembic 到达 head。

`POSTGRES_PASSWORD` 为必填项，Compose 不提供生产默认密码。本地 DBeaver 调试端口默认是
`127.0.0.1:15432`，只允许本机访问；可用 `POSTGRES_PORT` 调整本机端口。已有 PostgreSQL
数据卷不会因为修改环境变量自动更新数据库角色密码，调整密码前应先完成备份和角色变更。

## Unlimited-OCR

PDF 解析使用独立 GPU 推理服务，不将 Unlimited-OCR 模型、CUDA 或
`trust_remote_code` 放入 API/Worker 镜像。按官方说明部署固定版本的 vLLM/SGLang 服务后，
设置：

```text
CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__ENABLED=true
CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__BASE_URL=http://unlimited-ocr:10000
CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__MODEL=Unlimited-OCR
```

生产环境应固定模型 revision 和容器 digest，禁止运行时从不受控来源下载代码。OCR 网络只
允许 API 到推理服务，推理服务不应访问 PostgreSQL、Redis 或公网。HTML/DOCX 原生解析不
依赖 OCR 服务；OCR 未启用时 PDF 上传返回 `SERVICE_UNAVAILABLE`。

## Cross-Encoder/BGE Reranker

Reranker 默认关闭，支持本地 SentenceTransformers 和独立 HTTP 服务两种后端。

本地后端先安装可选依赖：

```bash
pip install -e ".[reranker]"
```

再配置：

```text
CI_ASSISTANT__KNOWLEDGE__RERANKER__BACKEND=local
CI_ASSISTANT__KNOWLEDGE__RERANKER__MODEL=BAAI/bge-reranker-v2-m3
CI_ASSISTANT__KNOWLEDGE__RERANKER__DEVICE=cpu
CI_ASSISTANT__KNOWLEDGE__RERANKER__BATCH_SIZE=16
CI_ASSISTANT__KNOWLEDGE__RERANKER__MAX_LENGTH=512
```

模型在每个 Worker 进程内懒加载并缓存。Celery prefork 会让不同进程分别持有一份模型，
应根据内存或显存容量调整 Worker 并发。生产环境建议预下载固定 revision，并设置
`LOCAL_FILES_ONLY=true`。

HTTP 后端不需要在平台安装模型依赖，配置如下：

```text
CI_ASSISTANT__KNOWLEDGE__RERANKER__BACKEND=http
CI_ASSISTANT__KNOWLEDGE__RERANKER__BASE_URL=http://reranker:8080
CI_ASSISTANT__KNOWLEDGE__RERANKER__ENDPOINT=/rerank
CI_ASSISTANT__KNOWLEDGE__RERANKER__MODEL=BAAI/bge-reranker-v2-m3
CI_ASSISTANT__KNOWLEDGE__RERANKER__TIMEOUT_SECONDS=15
CI_ASSISTANT__KNOWLEDGE__RERANKER__CANDIDATE_MULTIPLIER=4
```

请求契约包含 `model`、`query`、`documents` 和 `top_n`；响应兼容
`results[index,relevance_score]` 或 `data[index,score]`。服务不可用、超时或响应非法时，
Worker 自动使用原 Hybrid 排序继续诊断。本地模型加载/推理失败也使用相同降级路径。
两种后端升级前后都应运行同一离线 RAG 评测集。

## Embedding cache

Embedding cache 默认启用，默认文件为知识存储目录下
`embedding-cache/embeddings.sqlite3`。缓存仅保存模型、维度、归一化参数、文本 SHA-256
与 float32 向量，不保存知识原文；超出 `embedding_cache_max_entries` 后按最近访问时间
回收。缓存不可用或损坏时 Worker 会告警并直接计算，不影响索引任务。

每个 Worker 实例使用本地 SQLite；多主机不会共享缓存。模型、维度或归一化配置变化会自然
产生不同 cache key。容量调整使用
`CI_ASSISTANT__KNOWLEDGE__EMBEDDING_CACHE_MAX_ENTRIES`，紧急禁用使用
`CI_ASSISTANT__KNOWLEDGE__EMBEDDING_CACHE_ENABLED=false`。清理缓存前应停掉相关 Worker；
缓存可重建，不属于业务备份。

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
- PDF 解析失败：检查 Unlimited-OCR 地址、GPU 服务状态、页数/像素限制和请求超时。
- Reranker 未生效：检查 enabled、服务地址、模型名和 Worker 日志中的安全降级提示。
- Embedding cache 异常：检查知识卷写权限和磁盘容量；可禁用缓存后继续直接计算。
- Provider 失败：调用连接测试 API，检查最小只读 Token 权限。
- 模型不可用：诊断会输出低置信度 fallback，并在 Trace 记录 `fallback_used`。
