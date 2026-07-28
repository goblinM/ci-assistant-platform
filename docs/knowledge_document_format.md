# 知识文档规范

平台接受 Markdown、JSON、HTML、DOCX 和 PDF。文本内容最多 5,000,000 字符，文件上传
默认最多 20,000,000 字节。

推荐 Markdown 结构：

```markdown
# 错误名称
## 现象
## 适用 Provider
## 根因
## 排查步骤
## 解决方案
## 验证方式
```

每份文档必须提供标题、作用域和来源类型。外部公共知识还应提供 `source_url` 和
`license`。上传内容会执行 Secret Mask、规范化、SHA-256 去重、结构切片和后台索引。

作用域规则：

- `tenant_id` 必填，禁止跨租户召回。
- `project_id` 为空表示租户全局，否则只对指定项目生效。
- `provider` 为空表示通用，否则只用于 GitLab、Jenkins 或 GitHub。
- 更新同标题和作用域的文档会增加版本，旧版本变为 `superseded`。
- 删除为逻辑删除并触发新索引版本；原子切换后旧 Chunk 不再召回。

禁止上传访问令牌、Cookie、个人敏感信息、无授权整站抓取内容和无法追踪来源的模型生成回答。

格式处理边界：

- HTML 只提取上传文件中的标题和正文，不加载脚本、样式或任何外部资源。
- DOCX 检查 ZIP 成员数、解压后大小和压缩比，再提取标题与段落。
- PDF 在页数、DPI 和总像素限制内渲染，并发送到独立 Unlimited-OCR 服务。
- 加密 PDF、超限文件、无正文文档和不支持的扩展名会被拒绝。
- 所有解析结果继续执行 Secret Mask、SHA-256 去重、Chunk 和 Provider ACL。
