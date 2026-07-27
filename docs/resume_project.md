# 简历项目描述最终版

## 项目名称

AI CI 日志分析助手

## 一句话描述

基于 FastAPI、LLM、RAG 和规则工具上下文构建的 CI 失败日志分析服务，可自动识别失败类型、生成排查建议，并返回可追溯的知识库引用。

## 简历版项目描述 1：后端 / AI 工程化

设计并实现 AI CI 日志分析助手，面向 Python 项目 CI 构建和测试失败场景，提供日志输入、错误分类、原因分析、排查建议和知识库引用能力。
项目使用 FastAPI 提供服务接口，Pydantic 约束结构化输出，接入 OpenAI-compatible LLM 完成日志语义分析，并基于 SentenceTransformer + FAISS 构建本地知识库检索链路。
针对 RAG 场景，将检索到的知识片段作为 prompt 上下文，同时由后端统一回填 references，保证引用来源可追溯、可评测。
额外实现规则版工具上下文，模拟查询历史失败案例和流水线信息，提升分析结果的业务上下文相关性。

## 简历版项目描述 2：AI 效能 / Agent 方向

构建面向研发效能场景的 AI CI 排障助手，将 CI 失败日志、团队故障手册、历史失败 case 和 pipeline/job 上下文整合进 LLM 诊断链路，输出可追溯、可校验、可评测的结构化分析结果。
项目覆盖 LLM Prompt 约束、RAG 检索增强、规则版 Tool Context、GitLab Job 接入、敏感信息脱敏、fallback 降级和离线评测，为后续 PR 自动评论、Issue 创建和受控 Tool Calling 的 CI 排障 Agent 打基础。

## 技术栈

- Python / FastAPI / Uvicorn
- Pydantic / pydantic-settings
- OpenAI-compatible LLM API
- SentenceTransformer / FAISS / NumPy
- Pandas / HTTPX
- Docker

## 个人职责

- 设计 CI 日志分析接口和结构化响应 schema，约束 `error_type`、`suggestions`、`confidence`、`references` 等字段。
- 构建 prompt 模板，支持普通 LLM、RAG、RAG + 工具上下文三种分析链路。
- 整理本地知识库，使用 SentenceTransformer 生成 embedding，并通过 FAISS 实现 top-k 语义检索。
- 设计 references 回填机制，由服务端使用真实检索结果覆盖模型输出，避免 LLM 编造引用。
- 接入 GitLab Job 分析雏形，支持拉取 job trace、提取关键错误行、脱敏后进入 AI 分析链路。
- 设计 trace_id、fallback_used、日志耗时等观测字段，为审计和问题定位预留接口。
- 实现评测脚本，统计 schema 有效率、错误类型准确率、引用命中率和关键词覆盖率。
- 完成工程化整理，包括 README、Dockerfile、环境变量样例、API 示例和项目讲解材料。

## 项目亮点

- 从“直接问模型”升级到“检索知识 + 工具上下文 + 结构化校验”的可落地链路。
- 通过 Pydantic 对 LLM 输出做强约束，减少不可控自然语言输出对下游系统的影响。
- RAG 引用由后端检索结果决定，提升引用可信度和评测可解释性。
- 建立最小评测闭环，用指标定位问题是出在模型判断、检索召回还是 prompt 表达。
- 引入 GitLab Job、trace 脱敏、fallback 和 trace_id，体现从 Demo 走向产品化的工程意识。

## 面试可量化表达

可以这样说：

```text
我没有只验证接口能不能返回，而是为项目准备了离线评测集。每条样例标注期望错误类型、关键词和引用文档，评测脚本会统计 schema 有效率、错误类型准确率、RAG 引用命中率和关键词覆盖率。这样每次改 Prompt、模型或知识库，都能定位质量变化来自哪一层。
```

## 最终简历 bullet

```text
- 设计并实现 AI CI 日志分析助手，基于 FastAPI 提供 CI 失败日志诊断接口，支持普通 LLM、RAG 增强、RAG + 工具上下文和 GitLab Job 分析链路。
- 使用 Pydantic 定义结构化响应 schema，约束 error_type、confidence、suggestions、references 等字段，并对 LLM 输出执行 JSON 解析和二次校验。
- 基于 SentenceTransformer + FAISS 构建本地知识库检索，召回故障手册和历史 case，并由后端回填 references，避免模型编造引用。
- 设计规则版 Tool Context，模拟查询历史失败记录和 pipeline/job 上下文，提升分析建议与具体项目场景的相关性。
- 增加 timeout、retry、fallback、trace_id、敏感信息脱敏和离线评测脚本，统计 schema 有效率、错误类型准确率、引用命中率和关键词覆盖率。
```

## 可量化结果示例

在 20 条 CI 失败样例上进行离线评测：

- Schema valid rate：100%
- Error type accuracy：约 80%
- 指标覆盖：错误类型准确率、RAG 引用命中率、关键词覆盖率

实际数值可根据最新评测结果更新。
```

## 项目不足与诚实表达

面试时可以主动说：

- 真实 GitLab/Jenkins 接入还处于雏形，当前工具上下文仍以 mock 为主。
- 评测集规模有限，关键词指标只能粗略衡量建议质量。
- 权限、审计存储、用户反馈接口和 Dashboard 还未完整实现。
- Tool Calling 当前是规则版，下一步会升级为模型可选择但后端受控的工具调用。

这样讲会更可信，也能自然引出后续技术规划。
用户请求
  ↓
日志清洗
  ↓
RAG 检索
  ↓
Tool Context 查询
  ↓
Prompt 构造
  ↓
LLM 调用
  ↓
JSON 解析
  ↓
Pydantic 校验
  ↓
结果返回
```
