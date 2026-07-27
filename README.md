# CI Assistant Platform

可私有化部署的 CI 失败诊断平台。统一接入 GitLab 和 Jenkins，通过 PostgreSQL、
Redis/Celery、版本化 FAISS 知识索引以及 OpenAI-compatible 或本地规则诊断网关，
生成可追踪、带真实引用的结构化诊断。

## 产品定位

这个项目定位为“研发效能平台中的 AI 排障助手”，优先解决 CI 失败后开发者需要翻日志、查历史 case、问同事和重复定位的问题。

目标用户：

- 开发工程师：快速理解 CI 失败原因和下一步排查动作。
- DevOps / 平台工程师：沉淀高频失败类型、知识库和排障流程。
- 技术负责人：观察失败趋势、减少重复沟通和低效排障时间。

核心价值：

- 把非结构化 CI 日志转成稳定 JSON。
- 用 RAG 引入团队故障手册和历史经验。
- 用工具上下文补充 pipeline/job 运行时信息。
- 用评测脚本衡量 schema、分类、引用和关键词覆盖质量。
- 为后续自动评论 PR、创建 issue、推荐修复方案和 Agent 化排障打基础。

## 功能能力

- `/api/v1/diagnoses/logs` 与 `/runs` 统一诊断入口
- GitLab/Jenkins Provider、连接测试、只读工具和已验证 Webhook
- PostgreSQL 业务持久化、Redis/Celery 异步任务与 Alembic 迁移
- Markdown/JSON 知识上传、确定性本地 Embedding、版本化 FAISS 原子发布
- tenant/project/provider ACL 混合检索与真实 references
- Bearer API Key 租户隔离、Secret Mask、结构化校验、降级和 Prometheus 指标
- 18 Case GitLab/Jenkins 固定评测集及 Docker Compose 五服务部署

## 架构图

```mermaid
flowchart TD
    A["Developer / CI Webhook / GitLab Job"] --> B["FastAPI Router"]
    B --> C{"Analyze Mode"}
    C --> D["LLM Only"]
    C --> E["RAG"]
    C --> F["RAG + Tool Context"]
    C --> G["GitLab Job Fetch"]

    G --> H["Trace Extract + Mask Secrets"]
    H --> F

    E --> I["Local Retriever"]
    F --> I
    I --> J["Knowledge Docs"]
    I --> K["Embedding + FAISS"]
    K --> L["Top-k References"]

    F --> M["Rule Tools"]
    M --> N["Failure History"]
    M --> O["Pipeline Context"]

    D --> P["Prompt Builder"]
    L --> P
    N --> P
    O --> P
    P --> Q["LLM API"]
    Q --> R["JSON Parse"]
    R --> S["Pydantic Validate"]
    S --> T["Structured Diagnosis"]
    T --> U["Trace Log + Evaluation"]
```

## 目录结构

```text
ci-assistant-platform/
├── ci_assistant/              # 0.5.0 平台主包与默认运行链路
├── ci_analysis_demo/          # 旧 API 兼容包
│   ├── clients/               # GitLab API client
│   ├── core/                  # 配置与日志
│   ├── knowledge_docs/        # RAG 知识库与评测样例
│   ├── prompts/               # LLM prompt 模板
│   ├── routers/               # FastAPI 路由
│   ├── schemas/               # Pydantic 请求/响应模型
│   ├── scripts/               # 离线评测脚本
│   ├── services/              # LLM、RAG、工具上下文服务
│   ├── tools/                 # 规则工具与 mock 数据源
│   ├── utils/                 # 依赖注入、异常、fallback、timer
│   └── main.py                # 应用入口
├── docs/                      # 产品化、架构、评测、简历和面试材料
├── Dockerfile
├── Makefile
├── pyproject.toml
├── .env.example
└── requirements.txt
```

## 快速启动

```bash
cp .env.example .env
cp config.example.yml config.yml
docker-compose up -d --build
curl http://127.0.0.1:8080/health/ready
```

本地开发：

```bash
python -m venv venv
venv/bin/pip install -e ".[dev]"
venv/bin/alembic upgrade head
venv/bin/uvicorn ci_assistant.main:app --reload --port 8080
```

项目开发安装推荐使用：

```bash
pip install -e ".[dev]"
pytest
```

## 平台配置

新平台配置采用以下覆盖顺序：

```text
代码默认值 < config.yml < 环境变量 < Secret 文件
```

复制配置模板后，可通过环境变量指定配置和 Secret 目录：

```bash
cp config.example.yml config.yml
export CI_ASSISTANT_CONFIG=config.yml
export CI_ASSISTANT_SECRET_DIR=secrets
```

普通环境变量（如 `LLM_API_URL`）和嵌套变量（如
`CI_ASSISTANT__KNOWLEDGE__CONTEXT_MAX_CHARS`）均受支持。Secret 文件名使用对应环境变量名，
文件内容为值，例如 `secrets/LLM_API_KEY`。`config.yml` 和 `secrets/` 默认不会提交到 Git。

平台数据层使用 SQLAlchemy 2.x 异步接口和 `asyncpg`。`Database` 负责 Engine 生命周期和
事务级 Session：上下文正常退出时提交，发生异常时回滚，Repository 本身不擅自提交事务。

接口文档：

```text
http://127.0.0.1:8080/docs
```

容器状态和日志：

```bash
docker-compose ps
docker-compose logs -f api worker
```

## API 示例

生产环境 API 使用 Bearer API Key，并由 `API_KEYS_JSON` 将 Key 绑定到租户。开发环境未配置
API Key 时可直接调用。

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/diagnoses/logs" \
  -H "Authorization: Bearer ${CI_ASSISTANT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "log_text": "ModuleNotFoundError: No module named requests"
  }'
```

旧 `ci_analysis_demo` 接口在迁移兼容期继续保留，其示例如下：

RAG + 工具上下文分析：

```bash
curl -X POST "http://127.0.0.1:8080/ci/analyze-log" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "demo-project",
    "pipeline_id": "pipeline-001",
    "job_name": "unit-test",
    "log_text": "ModuleNotFoundError: No module named requests",
    "use_rag": true,
    "use_tools": true,
    "tool_mode": "rule"
  }'
```

响应结构：

```json
{
  "error_type": "dependency_missing",
  "summary": "缺少 requests 依赖，导致模块导入失败。",
  "reason": "日志中出现 ModuleNotFoundError，说明当前运行环境未安装 requests。",
  "suggestions": [
    "检查 requirements.txt 是否声明 requests",
    "确认 CI 中执行了 pip install -r requirements.txt"
  ],
  "confidence": "high",
  "references": [
    {
      "id": "docs-001",
      "title": "Python 构建中 ModuleNotFoundError 排查",
      "source": "故障手册",
      "content": "...",
      "category": "dependency",
      "tags": ["python", "ci"]
    }
  ],
  "trace_id": "optional-trace-id",
  "fallback_used": false
}
```

更多示例见 [API 示例](docs/api_examples.md)。

## 评测

启动服务后运行：

```bash
make eval
make eval-rag
```

核心指标：

- Schema valid rate：响应是否符合 Pydantic schema
- Error type accuracy：错误类型是否命中标注
- Top-k reference hit rate：RAG 引用是否命中期望知识文档
- Avg keyword score：原因和建议是否覆盖关键排查词

## 产品边界

0.5.0 默认只分析和建议，不自动修改代码或重跑 Pipeline。部署方仍需提供最小权限
CI Token、TLS、网络出口策略、备份、镜像扫描和 API Key 轮换。GitHub Actions、
Web 管理页、自动评论和人工审批后的写操作属于后续版本。

完整设计见 [产品化设计](docs/productization_design.md)。

## 工程化材料

- [CI 智能诊断平台产品化分析](docs/ci_assistant_platform_analysis.md)
- [CI 智能诊断平台 MVP](docs/ci_assistant_platform_mvp.md)
- [CI 智能诊断平台开发文档](docs/ci_assistant_platform_development.md)
- [CI 智能诊断平台开发跟进](docs/ci_assistant_platform_tracker.md)
- [产品化设计](docs/productization_design.md)
- [架构说明](docs/architecture.md)
- [API 示例](docs/api_examples.md)
- [评测说明](docs/evaluation.md)
- [RAG 和 Tool Calling 区别](docs/rag_vs_tool_calling.md)
- [Tool 调用优化全过程](docs/tool_calling_optimization.md)
- [今日面试速查](docs/interview_today_guide.md)
- [Agent 技术面试速查](docs/agent_concepts_interview_guide.md)
- [简历项目描述最终版](docs/resume_project.md)
- [面试专项题库](docs/interview_qna.md)
- [3 分钟自我介绍与 8 分钟项目讲解](docs/presentation_scripts.md)
- [项目讲解稿](docs/interview_script.md)

## 简历一句话

基于 FastAPI、LLM、RAG、Tool Context 和 Pydantic 构建 AI CI 日志分析助手，将 CI 失败日志转化为可追溯、可评测、可集成的结构化诊断结果，为研发效能平台中的自动化排障和 Agent 化工作流打基础。

## 后续路线

- 增加用户反馈入口，沉淀 accepted/rejected/helpful 标签。
- 引入 reranker 和 embedding cache，提高 RAG 命中率和性能。
- 接入 GitHub Actions Provider 和更多知识文档格式。
- 在人工审批边界内增加评论、Issue 和 Pipeline 重跑动作。
