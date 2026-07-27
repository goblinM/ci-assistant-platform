# 3 分钟自我介绍与 8 分钟项目讲解

## 1. 3 分钟自我介绍

面试官您好，我主要关注 Python 后端和 AI 工程化方向，最近在系统学习并实践 AI 效能项目，重点是把大模型能力放进真实研发流程里，而不是只做聊天式 Demo。

我当前做的项目是 AI CI 日志分析助手，场景来自研发团队里非常高频的 CI 构建和测试失败。传统方式下，开发同学需要手动翻日志、查历史经验、问 DevOps 或重新跑 pipeline，效率比较低。我希望用 LLM、RAG 和工具上下文，把这件事变成一个可服务化、可评测、可持续优化的诊断流程。

技术上，我用 FastAPI 搭建后端接口，用 Pydantic 约束请求和模型输出，用 OpenAI-compatible API 做日志语义分析。后续又加入了本地知识库 RAG，通过 SentenceTransformer 和 FAISS 检索故障手册和历史 case；同时加入规则版工具上下文，模拟查询历史失败和 pipeline/job 信息。模型返回后不会直接透传，而是经过 JSON 解析、Pydantic 校验、references 回填和异常分层，保证输出可集成。

我比较重视 AI 项目的工程闭环，所以项目里也做了评测脚本，统计 schema 有效率、错误类型准确率、引用命中率和关键词覆盖率。这样每次改 Prompt、模型或知识库，都能知道效果变化在哪里。

这个项目对我来说不只是一个学习项目，它也对应 AI 效能专家和 AI Agent 开发工程师的核心能力：识别研发流程痛点，把模型接入工程系统，控制输出边界，设计反馈和评测闭环。后续我计划继续补真实 GitLab/Jenkins 接入、用户反馈、审计权限和标准 Tool Calling，让它从分析助手逐步演进成可落地的 CI 排障 Agent。

## 2. 8 分钟项目讲解

### 0:00 - 1:00 项目背景

这个项目叫 AI CI 日志分析助手，目标是解决 CI 失败后的排障效率问题。

在日常研发里，CI 失败非常高频，但失败日志通常很长，开发者要自己找关键报错、判断是依赖问题、测试失败、环境变量缺失还是仓库权限问题。很多时候还要查历史 case 或问平台同学。

所以我设计了一个 AI 效能服务：输入 CI 日志，输出错误类型、摘要、原因、建议、置信度和引用依据。它可以作为研发效能平台里的一个诊断能力，也可以继续升级成 Agent 工具。

### 1:00 - 2:00 整体架构

项目后端使用 FastAPI，主要有四条接口链路：

- `/ci/analyze-log`：统一日志分析入口，通过 `use_rag/use_tools/tool_mode` 选择纯 LLM、RAG、规则 Tool 或自主 Tool。
- `/ci/analyze-gitlab-job`：获取真实 GitLab Job 和 Trace 后复用统一分析链路。
- 原有 RAG 和 Tool 专用 URL 仅作为兼容评测接口保留。
- `/ci/analyze-gitlab-job`：根据 GitLab job 拉取 trace 后分析。

整体流程是：请求进入 router，service 层构造 Prompt；如果开启 RAG，就从知识库检索 top-k 文档；如果开启工具上下文，就查询历史失败和 pipeline 信息；然后调用 LLM，最后做 JSON 解析和 Pydantic 校验，返回结构化结果。

### 2:00 - 3:00 为什么要 RAG

直接问模型可以处理常见错误，但建议容易比较泛。比如看到 `ModuleNotFoundError`，模型通常会说安装依赖，但它不知道团队 CI 里具体是 `requirements.txt`、私有源 token 还是 runner 镜像问题。

RAG 的作用是把团队故障手册、FAQ、历史 case 检索出来，让模型基于这些资料回答。项目里使用 SentenceTransformer 生成 embedding，用 FAISS 做 top-k 检索。

一个关键设计是 references 不让模型自己编，而是由后端使用真实检索结果回填。这样引用可追溯，也能评测引用命中率。

### 3:00 - 4:00 Tool Context 设计

RAG 解决的是知识问题，Tool Context 解决的是运行时上下文问题。

比如同样是依赖缺失，如果工具能查到当前 job 是 `unit-test`，runner 是 `python-runner`，历史 case 里同项目出现过 requests 缺失，那模型给出的建议就会更贴近实际。

当前项目先做规则版工具上下文：服务端根据日志关键词查询 mock 历史失败和 pipeline/job 信息。这样比一开始就让模型自主调用工具更稳定，也更好调试。后续可以升级为标准 Tool Calling。

### 4:00 - 5:00 结构化输出和可靠性

AI 工程里一个重点是不能直接信任 LLM 输出。

我在 Prompt 里要求模型输出 JSON，但后端仍然会做 `json.loads` 和 Pydantic 校验。Schema 里限制了 `error_type`、`confidence`、`suggestions` 和 `references` 的结构。这样即使模型输出缺字段或非法枚举，也不会进入下游系统。

另外我做了 timeout、retry、自定义异常和 fallback。比如 LLM 不可用时，可以使用规则 fallback 返回基础诊断，避免接口完全不可用。

### 5:00 - 6:00 评测闭环

我没有只停留在接口能返回，而是做了离线评测脚本。

评测样例里有日志、期望错误类型、期望关键词和期望引用。脚本调用服务后统计四类指标：

- schema valid rate：结构是否稳定。
- error type accuracy：分类是否正确。
- top-k reference hit rate：RAG 是否命中资料。
- avg keyword score：建议是否覆盖关键排查词。

这个设计的好处是能定位问题。如果 schema 低，是输出格式问题；如果 reference hit 低，是检索问题；如果 keyword score 低，可能是 Prompt 或知识库内容不足。

### 6:00 - 7:00 产品化设计

如果做成产品，我会按三步走。

第一步接入真实 CI 平台，例如 GitLab webhook，自动获取失败 job trace，提取关键行并脱敏。

第二步增加反馈闭环，让开发者标记 helpful、not helpful、accepted suggestion，并把这些反馈沉淀到评测集和知识库。

第三步补权限、审计和安全边界。用户只能分析自己有权限的项目；请求记录 trace_id、项目、job、模型版本、耗时和 fallback；日志中的 token、password、secret、api_key 必须脱敏；默认只做建议，不自动改代码或重跑 pipeline。

### 7:00 - 8:00 项目总结和后续

这个项目的价值不在于简单调用模型，而是把 LLM 放进一个可控的研发效能链路里：有知识检索、有工具上下文、有结构校验、有评测闭环，也考虑了产品化中的权限、安全和审计。

目前不足也很明确：真实平台接入还需要加强，工具调用还是规则版，评测样例规模有限，用户反馈和 Dashboard 还没做。

后续我会继续做四件事：接真实 GitLab/Jenkins API，增加反馈接口和评测回归，加入 reranker 和 embedding cache，最后把规则工具升级成受控 Tool Calling，让它逐步变成 CI 排障 Agent。

## 3. 30 秒极简版

我做了一个 AI CI 日志分析助手，面向研发效能场景。它用 FastAPI 提供接口，接收 CI 失败日志后，结合 LLM、RAG 知识库和工具上下文，输出错误类型、原因、建议、置信度和引用依据。项目重点不是简单调模型，而是做了 Pydantic 结构化校验、references 后端回填、异常 fallback 和离线评测，用 schema 有效率、错误类型准确率、引用命中率等指标衡量效果。后续可以接 GitLab/Jenkins webhook、PR 评论和用户反馈，演进成 CI 排障 Agent。
