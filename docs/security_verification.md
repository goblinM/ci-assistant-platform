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

仍需由部署方负责：Token 最小权限、网络出口策略、TLS 终止、镜像漏洞扫描、备份加密和
API Key 定期轮换。

GitHub 生产连接推荐使用短期 GitHub App Installation Token，只授予仓库 Metadata、
Actions 和 Contents 的读取权限；0.6.0 不需要 Actions 写权限。
