# Agent 技术面试速查：结合 AI CI 日志分析助手

## 1. 核心概念速记

### LLM

LLM 是大语言模型，本质是基于上下文生成下一个 token 的通用推理与生成能力。

在项目里：

- LLM 负责理解 CI 日志。
- 根据 Prompt 输出错误类型、原因、建议和置信度。
- 输出必须经过 JSON 解析和 Pydantic 校验，不能直接信任。

面试一句话：

> LLM 是推理和生成核心，但在工程系统里必须被 Prompt、Schema、RAG、Tool 和评测约束起来。

### Agent

Agent 是能围绕目标进行感知、规划、调用工具、观察结果并继续迭代的系统。

典型 Agent 结构：

```text
Goal / Task
  ↓
Plan / Reason
  ↓
Act / Tool Call
  ↓
Observe
  ↓
Update State
  ↓
Final Answer / Next Action
```

在项目里：

- 当前项目已经具备 Agent 的基础组件：LLM、RAG、Tool、trace、fallback、评测。
- 但还不是完整自主 Agent，因为还没有持续多轮任务循环、长期记忆和真实写入动作。

面试一句话：

> 我的项目目前是 Agent-ready 的 AI 效能服务，已经有 RAG、Tool 执行层和评测闭环，下一步可以演进为 CI 排障 Agent。

### Tool

Tool 是 Agent 可以调用的外部能力。

在项目里：

- `query_failure_history`
- `query_pipeline_context`
- `query_job_context`
- `check_dependency_file`
- `query_recent_commits`

这些工具通过 `ToolSpec`、`CI_TOOLS_SCHEMA`、`ToolsExecutor` 统一注册、筛选、执行和审计。

面试一句话：

> Tool 解决的是模型不能直接访问外部系统状态的问题，比如查 GitLab Job、依赖文件、历史失败和近期提交。

### Skill

Skill 是更高层的可复用能力包，通常包含操作步骤、提示词、工具组合、领域知识和执行约束。

Tool 更像一个 API 或函数；Skill 更像一套 SOP。

例子：

- Tool：`check_dependency_file(project_id, package_name)`
- Skill：`Python CI 依赖缺失排障流程`，包含读取日志、提取包名、检查依赖文件、检索历史 case、生成建议。

在项目里：

- 目前还没有显式 Skill 系统。
- 但 `docs/tool_calling_optimization.md` 和 Prompt 模板已经具备沉淀 Skill 的基础。

面试一句话：

> Tool 是单个动作，Skill 是可复用流程。我的项目现在有工具层，后续可以把高频排障路径沉淀成 Skill。

### MCP

MCP 可以理解为让模型或 Agent 标准化连接外部工具、资源和上下文的协议层。

它解决的问题：

- 不同工具接入方式不统一。
- Agent 需要稳定发现工具、调用工具、读取资源。
- 工具权限和边界需要标准化描述。

在项目里：

- 当前 `ToolsExecutor` 只实现了本地 `local` provider。
- `ToolSpec.provider` 已预留 `mcp`、`http`、`skill` 等扩展方向。

面试一句话：

> MCP 更像工具接入协议和生态标准；我当前项目先做本地 Tool 执行层，后续可以把 provider 从 local 扩展到 MCP。

### RAG

RAG 是检索增强生成：先从知识库检索资料，再让 LLM 基于资料回答。

在项目里：

- CI 日志先做 query 清洗。
- 根据 primary error 构建 metadata filter。
- 用 embedding + FAISS 召回知识文档。
- 用 keyword/rule rerank 优化排序。
- references 由后端真实检索结果回填。

面试一句话：

> RAG 解决模型缺少团队知识的问题，Tool 解决模型缺少系统实时上下文的问题。

## 2. Agent 的三种常见模式

### 2.1 ReAct

ReAct = Reason + Act。

模型一边推理，一边调用工具，再根据观察结果继续推理。

典型链路：

```text
Thought: 我需要确认是不是依赖缺失
Action: check_dependency_file
Observation: requirements.txt 中没有 requests
Thought: 依赖文件确实缺失
Final: 给出诊断和建议
```

项目对应：

- `tool_mode=llm` 接近 ReAct 的雏形。
- 第一轮 LLM 选择工具。
- 后端执行工具。
- 第二轮 LLM 基于工具结果生成最终诊断。

面试亮点：

> 我没有一开始让模型无限自主循环，而是做成两轮受控 ReAct：先选择工具，再诊断，便于审计、限流和安全控制。

### 2.2 Plan-and-Execute

先规划，再执行。

典型链路：

```text
Plan:
1. 提取日志关键错误
2. 检索知识库
3. 查询 pipeline 上下文
4. 检查依赖文件
5. 汇总结论

Execute:
逐步执行每个步骤
```

适合：

- 多步骤任务。
- 工具较多。
- 需要较强可解释性。

项目对应：

- 未来可以用于复杂 CI 排障。
- 比如 Docker 构建失败时，先读 Dockerfile，再查镜像拉取，再查 runner，再查最近提交。

### 2.3 Reflection / Self-Refine

模型先生成答案，再自我检查、修正或让另一个评审器评估。

典型链路：

```text
Draft Diagnosis
  ↓
Critique: 是否有证据？是否引用正确？建议是否可执行？
  ↓
Refined Diagnosis
```

项目对应：

- 可以用于提升建议质量。
- 可以让评审器检查 hallucination、references 是否支撑结论、建议是否可执行。

后续优化：

- 增加 `diagnosis_reviewer_prompt`。
- 对低置信度结果触发二次审查。
- 将审查结果纳入 `extra` 和评测。

## 3. Agent 和 Workflow 的区别

### Workflow

Workflow 是固定流程，路径由开发者定义。

例子：

```text
日志 -> RAG -> 工具上下文 -> LLM -> 校验 -> 返回
```

优点：

- 稳定。
- 可测试。
- 可审计。
- 成本可控。

缺点：

- 灵活性较低。
- 复杂未知问题处理能力弱。

### Agent

Agent 是动态流程，模型可以根据上下文决定下一步。

例子：

```text
日志 -> 模型判断需要查依赖文件 -> 查完后发现缺失 -> 再查近期提交 -> 最后诊断
```

优点：

- 灵活。
- 能处理未知组合问题。
- 更适合复杂任务。

缺点：

- 不稳定。
- 难评测。
- 成本和安全风险更高。

### 项目中的取舍

当前项目是 Workflow + 局部 Agent 能力：

- 统一入口和 rule tool 是 Workflow。
- `tool_mode=llm` 是受控 Agent 能力。
- 未来写入动作必须人机协同。

面试回答：

> 我不会把所有逻辑都交给 Agent。生产早期更适合 Workflow 保证稳定性，再在工具选择、复杂诊断等局部引入 Agent 能力。

## 4. 记忆管理

Agent 记忆通常分三类。

### 4.1 Short-term Memory

短期上下文，存在一次对话或一次任务中。

项目对应：

- 当前请求的 `log_text`
- `RAGResult`
- `ToolContext`
- `AnalysisTrace`
- `ToolRuntimeContext`

### 4.2 Episodic Memory

事件记忆，记录过去任务执行过程。

项目可扩展：

- 保存每次 CI 分析的 trace。
- 保存错误类型、工具调用、references、用户反馈。
- 后续遇到类似日志时检索历史分析。

### 4.3 Semantic Memory

语义知识，保存长期知识。

项目对应：

- `knowledge_docs.json`
- 故障手册
- FAQ
- 历史 case
- 构建规范

### 4.4 Procedural Memory

流程记忆，保存做事方法。

项目可扩展：

- 将“依赖缺失排障流程”沉淀成 Skill。
- 将“仓库权限失败排障流程”沉淀成 Skill。
- 将“Docker build 失败排障流程”沉淀成 Skill。

面试回答：

> 我的项目已经有短期上下文和语义知识库，下一步可以把分析 trace 变成 episodic memory，把高频排障 SOP 变成 procedural memory，也就是 Skill。

## 5. Harness 机制

Harness 可以理解为 Agent 的运行外壳和控制框架。

它负责：

- 组织模型调用。
- 管理工具 schema。
- 执行工具。
- 收集 observation。
- 控制最大轮数。
- 处理异常、超时、权限。
- 记录 trace。
- 做评测和回放。

在项目里的对应关系：

- `analyze_log_by_mode`：调度 harness。
- `ToolsExecutor`：工具执行 harness。
- `AnalysisTrace`：观测与审计。
- `_call_with_retry`：LLM 调用可靠性。
- `evaluate_ci_assistant.py`：评测 harness。

面试一句话：

> Harness 是把 LLM、Tool、状态、权限、评测串起来的执行框架。我的项目虽然没有叫 harness，但 `analyze_log_by_mode + ToolsExecutor + AnalysisTrace + eval script` 已经具备 harness 的核心职责。

## 6. OpenClaw 和 Hermes 区别

说明：以下是基于公开资料的高层对比，面试时建议讲概念，不要硬背具体 star 数或营销指标。

### OpenClaw

更偏平台型 Agent：

- 多渠道接入。
- skills / plugins / integrations 生态。
- agent workspace、routing、session 等运行时能力。
- 适合做多入口、多工具、多任务编排。

公开文档中 OpenClaw 强调 agent runtime、sessions、skills、plugin SDK、workspace 和多 agent routing。

适合场景：

- 个人或团队多渠道助手。
- 需要大量集成和技能生态。
- 需要平台化配置和多 agent 编排。

### Hermes

更偏记忆和自改进 Agent：

- 强调长期记忆。
- 强调从重复任务中学习。
- 更适合自托管、长期运行、重复工作优化。
- 常被描述为更重视 memory 和 repeated workflows。

适合场景：

- 长期个人助理。
- 需要记住用户偏好和任务历史。
- 重复工作自动化。

### 面试对比讲法

> OpenClaw 更像平台型 Agent 框架，强调多渠道、技能生态、插件和编排；Hermes 更强调长期记忆、自改进和重复任务优化。映射到我的项目，OpenClaw 的思路更像我现在做的 ToolSpec、ToolsExecutor、Skill 化扩展；Hermes 的思路更像后续要补的 episodic memory、用户反馈和历史诊断学习。

## 7. 结合项目的 Agent 问答

### Q1：你的项目是 Agent 吗？

答：

严格说当前是 Agent-ready 的 AI 效能服务，不是完全自主 Agent。它已经有 LLM、RAG、Tool Calling、trace、fallback 和评测，但还没有长期自主循环、长期记忆和自动执行写入动作。现在更像 Workflow + 局部 Agent 能力。

### Q2：为什么不直接做完全自主 Agent？

答：

CI 排障涉及代码、流水线、权限和可能的写入动作，安全边界很重要。生产早期我更倾向于稳定 Workflow，加受控 Tool Calling。等只读工具、评测和审计成熟后，再逐步开放评论 PR、创建 issue、重跑 pipeline 这类动作。

### Q3：你的 Tool Calling 怎么设计？

答：

我把工具抽象成 `ToolSpec`，包含 name、description、parameters_schema、provider、read_only、tags、trigger_keywords。工具通过 `CI_TOOLS_SCHEMA` 统一维护，再注册到 `ToolsExecutor`。执行器负责工具筛选、依赖注入、异常隔离、耗时记录和结果裁剪。

### Q4：rule tool 和 llm tool 有什么区别？

答：

rule tool 是服务端根据错误规则和上下文选择工具，稳定可控；llm tool 是模型第一轮自主选择工具，后端受控执行，再第二轮生成诊断。我的项目两种都支持，默认更推荐 rule，因为面向工程落地更稳定。

### Q5：如何防止 Agent 乱调工具？

答：

后端限制候选工具，而不是让模型看到所有工具。限制包括 read_only、allowed_tags、allowed_providers、max_tools、max_tool_calls。未知工具会被 executor 拒绝，单个工具异常不会打崩主流程。写入类工具未来必须走权限和人工确认。

### Q6：RAG 和 Tool 结果怎么进入 Prompt？

答：

RAG 结果通过 `RAGResult.to_prompt_context` 进入 Prompt，并受 context budget 控制。Tool 结果通过 `ToolContext.to_prompt_context` 或 tool result dump 进入 Prompt，并经过 result_trimmer 裁剪。这样控制 token 成本和上下文噪声。

### Q7：如何做 Agent 记忆？

答：

短期记忆是当前请求里的 trace、RAGResult、ToolContext。语义记忆是 knowledge_docs。下一步会把每次分析 trace 和用户反馈沉淀成 episodic memory，把高频排障 SOP 做成 Skill，也就是 procedural memory。

### Q8：如何评估 Agent？

答：

除了原有 schema valid、error_type accuracy、reference hit、keyword score，还要评估工具选择：tool precision、tool recall、tool success rate、tool latency p95、fallback rate、helpful rate 和 hallucination rate。

### Q9：Agent 和传统规则系统区别？

答：

规则系统稳定但覆盖有限；Agent 可以根据上下文动态选择工具和推理路径。我的项目不是抛弃规则，而是把规则作为稳定底座，用规则识别 primary error、限制工具候选，再让 LLM 在安全边界内增强诊断。

### Q10：你项目后续如何 Agent 化？

答：

路线是：

1. 扩大只读工具：读取依赖文件、测试报告、CI 配置、MR diff。
2. 增加记忆：历史诊断、用户反馈、团队 SOP。
3. 增加评审器：检查引用、幻觉和建议可执行性。
4. 增加人机协同写入动作：PR 评论、issue 草稿、pipeline 重跑建议。
5. 所有动作都记录审计，并支持回放和评测。

## 8. 今天面试里的高分表达

### 表达 1：Agent 不是越自主越好

> 我觉得工程里的 Agent 不是越自主越好，尤其是 CI/CD 场景涉及权限、代码和流水线动作。我的设计是先用 Workflow 保证稳定性，再在工具选择和复杂诊断里引入受控 Agent 能力。

### 表达 2：RAG 和 Tool 分层治理

> RAG 负责知识依据，Tool 负责运行时上下文，两者都进入 Prompt，但治理方式不同。RAG 的 references 由后端回填，Tool 的调用由 executor 限制权限和候选范围。

### 表达 3：Harness 是工程化核心

> Agent 的难点不只是 Prompt，而是 harness：怎么调度模型、执行工具、管理状态、处理失败、记录 trace 和做评测。我的项目里 `analyze_log_by_mode`、`ToolsExecutor`、`AnalysisTrace` 和评测脚本承担了这部分职责。

### 表达 4：记忆要分层

> 我不会把所有历史都塞进上下文，而是分短期上下文、语义知识、事件记忆和流程记忆。当前项目已有 RAG 语义知识和 trace，下一步会把用户反馈沉淀成 episodic memory，把高频排障路径沉淀成 Skill。

## 9. 反问面试官

- 你们现在的 Agent 更偏 Workflow 编排，还是模型自主工具调用？
- 团队是否有统一 Tool/MCP 接入层？
- Agent 评测会更关注任务成功率、工具调用准确率还是用户采纳率？
- 写入类工具，比如评论 PR、创建 issue、重跑流水线，权限边界怎么设计？
- 团队有没有长期记忆或用户反馈反哺机制？

## 10. 参考口径

OpenClaw / Hermes 的对比可作为面试中的行业观察，不建议讲得过细：

- OpenClaw：平台、skills、plugins、多集成、多 agent routing。
- Hermes：长期记忆、自改进、重复任务优化。
- 我的项目：当前更接近 OpenClaw 式工具和技能底座，后续要补 Hermes 式记忆和反馈学习。

参考资料：

- OpenClaw Agent runtime architecture: https://docs.openclaw.ai/agent-runtime-architecture
- OpenClaw Plugins: https://docs.openclaw.ai/plugins
- OpenClaw Tools / Skills / Plugins overview: https://github.com/openclaw/openclaw/blob/main/docs/tools/index.md
- Hermes Persistent Memory: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory/
- Hermes memory system overview: https://hermes-agent.ai/blog/hermes-agent-memory-system
