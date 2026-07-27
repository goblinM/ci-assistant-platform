# 面试项目讲解稿
## 自我介绍
AI 效能方向自我介绍
```
您好，我之前主要做 Python 后端和研发效能平台相关工作，过去几年比较聚焦内部流程系统、工单协同平台、研发数据量化平台以及 CI/CD 工程链路建设。

我比较擅长把复杂业务流程抽象成可配置、可扩展的平台能力，比如做过工单状态流转、SLA、自动验收、ONES/H3 系统集成，也做过 GitLab CI、SonarQube 质量门禁和 Runner 优化。

最近我也在往 AI 效能研发方向补充能力，做了一个 AI CI 失败智能诊断助手，基于 FastAPI、RAG、Tool Context 和 LLM，对 CI 失败日志做错误分类、原因分析和排查建议生成，同时补了评测、可观测和降级设计。

所以我的定位更偏 Python 平台工程和研发效能方向，希望能把后端工程能力、研发流程理解和 AI 应用能力结合起来，做真正能提升研发效率的平台型产品。
```

Python 后端 + AI 应用方向自我介绍
```
您好，我有多年 Python 开发经验，主要做过 Flask/Django 后端服务、内部平台系统、数据平台和系统集成类项目。

过去的项目里，我比较多接触复杂业务流程建模、接口开发、MySQL/Redis、异步任务、Webhook 回调、权限和数据统计，也参与过 CI/CD、质量门禁和自动化流程建设。

最近我在补 AI 应用开发能力，基于 FastAPI 做了一个 AI CI 失败分析服务，里面用到了 Pydantic 结构化校验、LLM API 调用、RAG 检索、FAISS 向量检索、Tool Context 和评测脚本。

我希望后续做 Python 后端或 AI 应用开发方向的工作，能把已有的平台开发经验和 AI 工程化能力结合起来。
```
## 1. 项目背景

这个项目是一个 AI CI 日志分析助手，目标是解决 CI 构建或测试失败后，开发同学需要人工翻日志、查历史经验、定位失败原因的问题。

最初版本只是把错误日志发给 LLM，让模型输出错误类型、原因和建议。后面我发现这种方式有两个问题：第一，模型容易给通用建议，不一定结合团队经验；第二，输出结果不稳定，不方便做自动化处理。所以我把它升级成了 FastAPI 服务，并加入 RAG、本地知识库、规则工具上下文和 Pydantic 校验。

## 2. 核心流程

用户请求进入 FastAPI 后，根据接口分成三条链路：

第一条是普通 LLM 分析：直接把日志拼进 prompt，要求模型返回结构化 JSON。

第二条是 RAG 分析：先用 SentenceTransformer 把日志转成向量，再用 FAISS 从知识库里检索 top-k 相关文档，把这些文档拼进 prompt，让模型基于知识片段回答。

第三条是 RAG + 工具上下文：除了知识库检索，还会根据日志提取关键字，查询 mock 的历史失败记录和 pipeline 上下文，再一起交给模型分析。

模型返回后，我会用 `json.loads` 解析，再用 Pydantic 的 `AnalysisLogResponse` 校验，保证输出字段和枚举合法。

## 3. 为什么要做 RAG

直接问模型时，它可以判断 `ModuleNotFoundError` 这类常见问题，但建议往往比较泛。RAG 的作用是把团队已有的故障手册、FAQ、历史 case 和构建规范检索出来，让模型参考这些资料回答。

比如日志里出现：

```text
ModuleNotFoundError: No module named requests
```

RAG 会检索到 `Python 构建中 ModuleNotFoundError 排查` 和 `Python 依赖缺失导致构建失败`，模型就能更明确地建议检查 `requirements.txt` 和 CI 依赖安装步骤。

## 4. references 为什么由后端回填

一开始我让模型自己输出 references，后来评测发现模型可能返回缺字段的引用，甚至编出不存在的引用，导致 Pydantic 校验失败或引用命中率很低。

所以我调整为：模型只负责分析，references 由 retriever 的真实 top-k 检索结果覆盖。这样引用可追溯，也方便评测。

这个设计能把 LLM 的不确定性限制在分析文本里，而不是让它影响证据来源。

## 5. 工具调用怎么做

当前是规则版工具调用，还不是完全让模型自主选择工具。

服务端会根据日志提取关键字，例如 `ModuleNotFoundError`、`403`、`KeyError`，然后查询两个 mock 工具：

- 历史失败案例
- pipeline/job 上下文

这样做的好处是稳定、容易调试，也适合项目早期。后续如果要升级，可以把这些工具注册成标准 function calling，让模型决定是否调用。

## 6. 评测怎么做

我准备了 20 条 CI 失败样例，每条标注：

- 期望错误类型
- 期望关键词
- 期望命中的知识库标题

评测脚本会调用接口，并统计四个指标：

- Schema valid rate：结构化输出是否有效
- Error type accuracy：错误类型是否正确
- Top-k reference hit rate：引用是否命中预期文档
- Avg keyword score：原因和建议是否覆盖关键排查词

这个评测帮助我定位问题到底是模型分类错、RAG 没检索到，还是 prompt 没约束好。

## 7. 遇到的问题和解决

第一个问题是模型返回 JSON 不稳定。我通过 prompt 约束和 Pydantic 二次校验解决。

第二个问题是 RAG references 校验失败。原因是模型返回的 references 缺少 `id/content/category/tags`，而 schema 要求完整字段。解决方式是 RAG 场景统一由后端用 retriever 结果覆盖 references。

第三个问题是本地评测请求出现空 502。后来定位到 httpx 可能继承系统代理，于是评测脚本使用 `trust_env=False`，避免本地请求走代理。

## 8. 后续优化

如果继续扩展，我会做四件事：

1. 接真实 GitLab/Jenkins API，替换 mock 工具。
2. 缓存 embedding 和 FAISS index，减少服务启动成本。
3. 引入 reranker，提高 RAG 引用排序质量。
4. 增加单元测试和 CI，覆盖 prompt 解析、schema 校验和检索命中。

## 9. 一句话总结

这个项目的价值不是简单调用 LLM，而是把 LLM 放进一个可控的工程链路里：有知识检索、有上下文工具、有结构化校验、有评测闭环，能更接近真实研发效能场景。

## 10. 产品化补充讲法

如果面试官追问“怎么从 Demo 变成产品”，我会按四个边界讲：

第一是用户流程。开发者可以手动粘贴日志，也可以由 GitLab/Jenkins webhook 自动触发分析。系统会提取关键错误行、脱敏、检索知识库、查询工具上下文，再返回诊断结果。

第二是反馈闭环。每次结果都带 `trace_id`，用户可以标记 helpful、not helpful 或修正 error_type，这些反馈进入评测集和知识库，形成回归评测。

第三是权限和审计。用户只能分析自己有权限的项目，系统记录 project、pipeline、job、模型版本、RAG 命中文档、工具调用、耗时和 fallback 状态。

第四是安全边界。当前只做分析和建议，不自动改代码；后续 PR 评论、创建 issue、重跑 pipeline 和自动修复 MR 会按风险级别逐步授权。
