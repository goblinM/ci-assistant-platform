# MVP 安全验证

已实现并自动测试：

- Bearer API Key 与租户绑定；平台连接管理仅管理员 Key 可访问。
- 健康检查、指标和已签名 Webhook 是明确的公开入口。
- GitLab/Jenkins Webhook 使用常量时间比较验证共享 Secret。
- GitHub Webhook 使用原始请求体和共享 Secret 校验 `X-Hub-Signature-256` HMAC-SHA256。
- 所有诊断 Tool 默认只读，并同时检查 enabled、Capability 和项目允许列表。
- 日志和知识在进入 Prompt/索引前执行 Secret Mask。
- Prompt 将日志、知识和 Tool Result 明确标记为不可信证据。
- PostgreSQL 唯一键和 `ON CONFLICT` 保证 Webhook 幂等。
- FAISS 检索强制 tenant/project/provider 过滤。
- 容器使用 `ci-assistant` 非 root 用户。
- HTML 解析不加载外部资源；DOCX 限制 ZIP 成员数、解压大小和压缩比。
- PDF 限制文件大小、页数、DPI 和总像素，GPU OCR 与业务数据服务网络隔离。
- Reranker 默认关闭；启用时只发送检索 query 和已通过 ACL 的候选知识片段，不发送
  Token、原始 Webhook Body 或完整 CI 日志，异常自动回退 Hybrid 排序。
- 诊断反馈按租户和诊断关联，评论写入前执行 Secret Mask；聚合接口不返回评论正文。
- Embedding cache 不保存知识原文，仅保存不可逆文本 hash、模型参数和向量；缓存失败自动
  退回直接计算。
- Agent P0 默认关闭且只允许现有只读 Provider Tool；模型不能提供租户 ID 或资源参数，
  候选集外工具、重复调用和预算越界由运行时阻断。
- Agent Step Trace 不保存 Observation 正文，只保存脱敏字段摘要、长度、截断状态和内容 Hash。

仍需由部署方负责：Token 最小权限、网络出口策略、TLS 终止、镜像漏洞扫描、备份加密和
API Key 定期轮换。

本地 Reranker 应固定模型 revision，生产环境推荐预下载模型并设置
`local_files_only=true`，禁止 `trust_remote_code`；Celery 多进程会分别持有模型，应按
内存/GPU 容量限制并发。HTTP Reranker 应固定镜像 digest，只允许 Worker 访问，且不得访问
PostgreSQL、Redis、CI Provider 或公网。若候选知识包含受限内部信息，HTTP 服务必须部署在
同一安全域并启用传输加密。

GitHub 生产连接推荐使用短期 GitHub App Installation Token，只授予仓库 Metadata、
Actions 和 Contents 的读取权限；0.6.0 不需要 Actions 写权限。
