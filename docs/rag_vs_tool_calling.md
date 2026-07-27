# RAG 和 Tool Calling 区别

## 一句话区别

RAG 是“先查资料，再让模型基于资料回答”；Tool Calling 是“让模型或服务端调用工具，获取外部系统的实时或结构化信息”。

## RAG 解决什么问题

RAG 主要解决模型缺少私有知识、团队经验和最新资料的问题。

在本项目里，RAG 查的是本地知识库：

```text
ci_analysis_demo/knowledge_docs/knowledge_docs.json
```

知识库里包括：

- CI 故障手册
- 常见错误 FAQ
- 历史 case
- 构建规范

流程是：

```text
日志 -> embedding -> FAISS 检索 top-k -> 拼入 prompt -> LLM 分析
```

适合的问题：

- `ModuleNotFoundError` 应该参考哪份排查手册？
- `pip install` 失败有哪些常见原因？
- Docker build 失败应该看哪些规范和历史 case？

## Tool Calling 解决什么问题

Tool Calling 主要解决模型需要访问外部系统或执行动作的问题。

在本项目里同时支持规则工具选择和 LLM 自主 Tool Calling。GitLab 工具通过真实 API 获取运行时数据：

- `query_failure_history`：查询历史相似失败
- `query_pipeline_context`：查询 pipeline/job 上下文
- `query_job_context`：查询 Job 详细信息
- `check_dependency_file`：检查仓库依赖文件
- `query_recent_commits`：查询近期提交

流程是：

```text
日志 -> primary_error -> 规则或 LLM 选择工具 -> 获取实时上下文 -> LLM 分析
```

适合的问题：

- 这个项目历史上有没有类似失败？
- 当前失败发生在哪个 job/stage？
- runner、branch、commit message 有什么上下文？

## 两者在项目里的关系

RAG 提供“知识依据”，Tool Calling 提供“运行时上下文”。

举例：

```text
ModuleNotFoundError: No module named requests
```

RAG 会检索到依赖缺失排查手册；Tool Calling 会补充历史失败里是否也出现过 requests 缺失，以及当前 pipeline/job 信息。

最终 prompt 同时包含：

- 原始日志
- 知识片段
- 工具查询结果

## 为什么 references 不让模型生成

RAG 的 references 应该代表真实检索结果。如果让模型自己生成，可能出现缺字段、编造引用、引用标题不匹配等问题。

所以本项目采用：

```text
模型负责分析结论
后端负责回填真实 references
```

这样引用可追溯，也方便评测 `Top-k reference hit rate`。

## 面试讲法

RAG 和 Tool Calling 都是在增强 LLM，但增强的方向不同。RAG 是把私有知识库检索出来给模型参考，解决“模型不知道团队资料”的问题；Tool Calling 是调用外部工具或系统拿上下文，解决“模型不能自己访问系统状态”的问题。

在我的项目里，RAG 查询故障手册、FAQ 和历史 case，Tool Calling 通过真实 GitLab API 查询 pipeline、job、依赖文件和近期提交。GitLab Job 入口只强制获取分析必需的 Job Trace，其余数据由工具按需补充，并通过请求级缓存避免重复 API 调用。两者最后都会进入 prompt，但 references 由 RAG 检索结果决定，不交给模型自由编造。
