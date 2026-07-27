# CI Assistant Platform API 示例

服务地址为 `http://127.0.0.1:8080`。生产环境请求增加
`Authorization: Bearer ${CI_ASSISTANT_API_KEY}`；示例租户由默认配置自动创建。

## 日志诊断

```bash
curl -X POST http://127.0.0.1:8080/api/v1/diagnoses/logs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}" \
  -d '{
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "log_text": "ModuleNotFoundError: No module named requests",
    "use_rag": true,
    "use_tools": false
  }'

curl http://127.0.0.1:8080/api/v1/diagnoses/DIAGNOSIS_ID \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}"
```

创建接口返回 `202`；查询结果包含状态、结构化诊断和真实检索引用。

## CI Run 诊断

```bash
curl -X POST http://127.0.0.1:8080/api/v1/diagnoses/runs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}" \
  -d '{
    "connection_id": "main-gitlab",
    "project_ref": "group/project",
    "run_id": "12345",
    "use_rag": true,
    "use_tools": true
  }'
```

Jenkins 使用相同接口，将 `connection_id` 指向 Jenkins 连接，`project_ref` 可使用
`folder/subfolder/job-name`。

## 连接

```bash
curl http://127.0.0.1:8080/api/v1/connections \
  -H "Authorization: Bearer ${CI_ASSISTANT_ADMIN_KEY}"

curl -X POST http://127.0.0.1:8080/api/v1/connections/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CI_ASSISTANT_ADMIN_KEY}" \
  -d '{"connection_id":"main-gitlab"}'
```

连接管理只接受映射为 `*` 的管理员 Key。

## 知识文档

```bash
curl -X POST http://127.0.0.1:8080/api/v1/knowledge/documents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}" \
  -d '{
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "provider": "gitlab",
    "title": "Python 依赖排障",
    "format": "markdown",
    "content": "# ModuleNotFoundError\n检查锁文件并重建隔离环境。",
    "source_type": "customer",
    "source_url": "https://docs.example.com/runbooks/python",
    "license": "Proprietary"
  }'

curl "http://127.0.0.1:8080/api/v1/knowledge/documents?tenant_id=00000000-0000-0000-0000-000000000001" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}"

curl -X DELETE \
  "http://127.0.0.1:8080/api/v1/knowledge/documents/DOCUMENT_ID?tenant_id=00000000-0000-0000-0000-000000000001" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}"
```

JSON 文档将 `format` 改为 `json`，`content` 传递 JSON 字符串。更完整的制作规则见
`knowledge_document_format.md`。

## Webhook

```bash
curl -X POST http://127.0.0.1:8080/api/v1/webhooks/main-gitlab/gitlab \
  -H "X-Gitlab-Token: ${GITLAB_WEBHOOK_SECRET}" \
  -H "Content-Type: application/json" \
  -d @gitlab-event.json

curl -X POST http://127.0.0.1:8080/api/v1/webhooks/main-jenkins/jenkins \
  -H "X-CI-Webhook-Token: ${JENKINS_WEBHOOK_SECRET}" \
  -H "Content-Type: application/json" \
  -d @jenkins-event.json
```

重复事件由数据库唯一键幂等处理。交互式完整 Schema 可查看 `/docs`。
