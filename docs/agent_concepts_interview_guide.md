# Agent 技术面试速查：结合 AI CI 日志分析助手

> 本文以 `ci_assistant` 0.6.2 主运行包为事实基线。旧包 `ci_analysis_demo` 中的
> `tool_mode=llm`、两轮工具选择等实现只作为历史原型参考，不代表当前主平台已经具备
> 模型驱动的多轮 Agent Loop。配套学习计划见
> [AI Agent 学习跟进清单](agent_learning_tracker.md)。

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
- 当前主平台由服务端按固定顺序执行日志预处理、RAG、候选只读工具和一次诊断调用。
- 但还不是完整自主 Agent，因为没有模型驱动的持续多轮任务循环、可恢复 Agent State、
  长期记忆和真实写入动作。

面试一句话：

> 我的项目目前是 Agent-ready 的 AI 效能服务，已经有 RAG、Tool 执行层和评测闭环，下一步可以演进为 CI 排障 Agent。

### Tool

Tool 是 Agent 可以调用的外部能力。

在项目里：

- `get_run_context`
- `get_job_context`
- `get_job_log`
- `get_changes`

这些工具通过 `ToolSpec`、默认工具注册表和 `ProviderToolExecutor` 统一注册、筛选和执行。
执行器同时检查 enabled、read-only、项目允许列表和 Provider Capability；当前 trace 记录
调用名称和结果状态，但尚未形成完整的逐步 Agent 轨迹审计。当前诊断编排器会直接获取
Job 日志，候选工具循环实际组装的是 run、job 和 changes 三类上下文参数。

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
- 但现有 Tool 注册表、CI 故障知识和排障文档已经具备沉淀 Skill 的基础。

面试一句话：

> Tool 是单个动作，Skill 是可复用流程。我的项目现在有工具层，后续可以把高频排障路径沉淀成 Skill。

### MCP

MCP 可以理解为让模型或 Agent 标准化连接外部工具、资源和上下文的协议层。

它解决的问题：

- 不同工具接入方式不统一。
- Agent 需要稳定发现工具、调用工具、读取资源。
- 工具权限和边界需要标准化描述。

在项目里：

- 当前主平台使用进程内 `ProviderToolExecutor` 调用统一 CI Provider 的只读能力。
- 还没有实现 MCP Host、Client 或 Server，也没有 MCP transport、session 和授权映射。

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

- 旧兼容包的 `tool_mode=llm` 曾提供两轮受控工具选择原型。
- 当前 `ci_assistant` 主平台并未继承该模式，而是由服务端根据日志关键词、Provider
  Capability 和参数完整性筛选工具，执行完成后进行一次诊断调用。

面试亮点：

> 当前主平台不是 ReAct，而是确定性 Workflow 加受控只读 Tool Calling。这样优先保证
> 稳定、可测试和可审计；下一步会在保留 Workflow 基线的前提下增加有界 Agent Loop。

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

当前项目是 Workflow + Agent-ready 基础能力：

- 主平台统一入口、RAG、候选工具和诊断调用是确定性 Workflow。
- Tool、trace、fallback 和评测是后续 Agent 化所需的基础设施。
- 旧兼容包的 `tool_mode=llm` 只能作为历史实验，不能说成主平台现行能力。
- 未来写入动作必须人机协同。

面试回答：

> 我不会把所有逻辑都交给 Agent。生产早期更适合 Workflow 保证稳定性，再在工具选择、复杂诊断等局部引入 Agent 能力。

## 4. 记忆管理

Agent 记忆通常分三类。

### 4.1 Short-term Memory

短期上下文，存在一次对话或一次任务中。

项目对应：

- 当前诊断请求中的预处理日志。
- 本次检索得到的 `Reference` 列表。
- 本次只读工具结果。
- 诊断级 `analysis_trace`。

这些是单次任务上下文和追踪数据，还没有统一的 Agent State 或 thread checkpoint。

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

- `DiagnosisOrchestrator`：编排日志预处理、RAG、工具和诊断网关。
- `ProviderToolExecutor`：候选工具筛选和二次权限校验。
- `analysis_traces`：保存诊断级追踪结果。
- Celery Worker：重试、异步执行和任务终态管理。
- 固定诊断、排序数据集及评测脚本：提供回归基线。

面试一句话：

> Harness 是把 LLM、Tool、状态、权限、失败处理和评测串起来的执行框架。我的项目已有
> Orchestrator、只读 Executor、Celery、trace 和评测基础，但还缺多轮状态、checkpoint、
> resume 和逐步轨迹评测。

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

> OpenClaw 更像平台型 Agent Runtime，强调多渠道、技能生态、插件和编排；Hermes 更强调
> 长期记忆、自改进和重复任务优化。映射到我的项目，OpenClaw 的思路更接近现有
> `ToolSpec`、`ProviderToolExecutor` 和未来 Skill 扩展；Hermes 的思路更接近后续要补的
> episodic memory、用户反馈和受控经验写入。

## 7. 结合项目的 Agent 问答

### Q1：你的项目是 Agent 吗？

答：

严格说当前是 Agent-ready 的 AI 效能服务，不是完全自主 Agent。它已经有 LLM、RAG、Tool Calling、trace、fallback 和评测，但还没有长期自主循环、长期记忆和自动执行写入动作。现在更像 Workflow + 局部 Agent 能力。

### Q2：为什么不直接做完全自主 Agent？

答：

CI 排障涉及代码、流水线、权限和可能的写入动作，安全边界很重要。生产早期我更倾向于稳定 Workflow，加受控 Tool Calling。等只读工具、评测和审计成熟后，再逐步开放评论 PR、创建 issue、重跑 pipeline 这类动作。

### Q3：你的 Tool Calling 怎么设计？

答：

我把主平台只读工具抽象成 `ToolSpec`，包含 name、description、func、capability、tags、
trigger_keywords、read_only 和 enabled。默认注册表集中维护工具，`ProviderToolExecutor`
先筛选候选，在执行时再次检查启用状态、只读属性、项目允许列表和 Provider Capability。

### Q4：rule tool 和 llm tool 有什么区别？

答：

当前主平台只有服务端确定性筛选：根据日志关键词、Provider Capability、项目允许列表和参数
完整性选择工具。旧兼容包曾实验模型选择工具，但不能描述成主平台现行能力。后续若增加
LLM Tool Selection，会保留当前模式作为稳定基线并做对照评测。

### Q5：如何防止 Agent 乱调工具？

答：

当前主平台不让模型直接决定工具。后端按 enabled、read_only、项目允许列表、Provider
Capability、触发关键词和最大调用数限制执行；执行阶段再次校验，单个工具异常会转换为
受控错误结果。未来开放模型选择时，未知工具、参数 Schema、超时和预算仍必须由宿主校验，
写入类工具必须走权限和人工确认。

### Q6：RAG 和 Tool 结果怎么进入 Prompt？

答：

主平台把预处理日志、真实检索引用和工具结果分别标记为 `CI LOG (untrusted)`、
`KNOWLEDGE (untrusted)` 和 `TOOLS (untrusted)` 后进入 Prompt。日志已有长度控制和脱敏，
但 Agent 化之前仍需补充统一的 observation 裁剪、总 context budget 和逐步压缩策略。

### Q7：如何做 Agent 记忆？

答：

当前项目只有单次诊断上下文、`analysis_trace` 和语义知识库，还没有完整 Agent Memory。
下一步可以在租户隔离和人工审核边界下，把诊断与反馈沉淀成 episodic memory，把高频排障
SOP 变成 procedural memory，也就是 Skill。

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

> Agent 的难点不只是 Prompt，而是 Harness：怎么调度模型、执行工具、管理状态、处理失败、
> 记录 trace 和做评测。我的项目里 `DiagnosisOrchestrator`、`ProviderToolExecutor`、Celery、
> `analysis_traces` 和固定评测承担了基础职责；checkpoint、resume 和逐步轨迹仍是后续工作。

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

## 11. 求职定位与当前能力基线

### 推荐定位

当前项目最适合支撑以下求职主线：

> Python 后端能力较强、具备 RAG、Tool Calling、评测和安全治理经验的 AI Agent 应用
> 工程师，并可扩展到 AI 平台工程、Agent 工程、AI Infra 应用层及研发效能/AIOps 岗位。

不建议把主要精力投入“大模型预训练/算法研究岗”。项目的差异化是 AI Agent 工程、Python
后端、CI/CD 领域、安全治理和评测闭环的组合，而不是模型训练。

### 已有能力

| 能力 | 证据等级 | 当前事实 |
| --- | --- | --- |
| FastAPI AI 应用平台 | implemented | API、鉴权、健康检查、指标和异步任务入口已实现 |
| 多 CI Provider 抽象 | implemented | GitLab、Jenkins、GitHub Actions 共享 `CIProvider` |
| RAG 工程链路 | implemented | FAISS、Hybrid Retrieval、ACL、Reranker 和真实引用 |
| Tool 安全执行层 | implemented | enabled、read-only、允许列表和 Capability 双重校验 |
| 结构化输出与降级 | implemented | Pydantic 结果、规则网关和模型失败 fallback |
| 异步可靠性基础 | implemented | Celery late ack、worker lost reject、退避重试和队列路由 |
| 评测与反馈 | implemented | 固定 Case、排序指标和租户级反馈接口 |
| AI 安全治理 | implemented | Secret Mask、租户 ACL、Webhook 验签和不可信 Prompt 分区 |

### 影响 Agent 定位的主要缺口

1. **模型驱动的多轮 Agent Loop**：当前工具由服务端确定性筛选，没有 observation 后的
   再规划。
2. **可恢复 Agent State**：没有 goal、step、observation、budget、stop reason 和
   checkpoint/resume 的统一状态。
3. **Agent Memory**：知识库属于 semantic memory；反馈和历史诊断尚未形成受控 episodic
   memory，高频排障流程也没有形成 procedural memory/Skill。
4. **Human-in-the-loop 状态机**：默认只读边界已实现，但尚无动作提案、审批、恢复和执行
   审计链路。
5. **Trajectory Evaluation**：已有结果与 RAG 评测，尚缺工具选择、任务成功、步骤效率、
   越权率、恢复率和成本指标。

面试时必须使用以下边界：

> 当前系统是 Agent-ready 的受控 CI 诊断 Workflow。下一步是在保留稳定基线的前提下，
> 增加有界 Agent Loop、持久化状态、人工审批和轨迹评测。

## 12. 学习资料优先级

### S 级：主线精学

1. **learn-claude-code**：第一优先级。重点学习 Agent Loop、工具结果回灌、任务状态、
   最大轮数、上下文压缩、错误恢复和 Harness，而不是只运行示例。
2. **Hello-Agents**：用于建立 Agent、ReAct、Planning、Reflection、Memory、Multi-Agent、
   Evaluation 和安全的完整知识地图；RAG 和 Prompt 基础可快速复习。
3. **LangChain/LangGraph**：先掌握 Message、Tool 和 Structured Output，再重点学习
   LangGraph State、Checkpoint、Persistence、Interrupt、Resume 和 Human-in-the-loop。
4. **nanobot**：精读相对小型的真实 Agent Runtime，重点关注 Agent Loop、Tool Registry、
   Session、Memory、Skill、Provider 和上下文构造。

学习 LangGraph 前应先手写最小 Agent Loop。否则容易只会框架 API，不能解释状态、停止条件、
错误恢复和权限边界。主平台也不应为了简历立即重写为 LangGraph，应先通过独立实验和评测
证明收益。

### A 级：面试强化

- **小林 Coding**：按 Agent、Tool Calling、RAG、LangChain/LangGraph、大模型工程顺序
  复盘。每道题先口述，再看答案，并补一个当前项目的真实锚点。
- **AgentGuide**：按 Agent 架构、RAG、Tool、MCP、评测、上下文工程和项目设计标签查漏。
- **ai-agent-interview-guide**：用于模拟追问、检查覆盖面和改进表达，不照搬项目与指标。

### B 级：架构选读

- **OpenClaw**：选读 Runtime、Workspace、Session、Tool Policy、Skills、Plugins 和多 Agent
  routing；不复刻整个通用平台。
- **Hermes Agent**：重点学习 Persistent Memory、Session Search、Skill 演进以及 Memory/
  Skill 写入审批。
- **Agent-Learning-Hub**：作为专项资料索引，不作为线性主教材。

建议时间分配：项目实践 30%，learn-claude-code 与手写 Loop 25%，LangGraph 20%，nanobot
源码 10%，面试训练 10%，OpenClaw/Hermes 选读 5%。

## 13. 项目演进优先级

以下内容是学习和设计建议，不等同于已经进入 `docs/TODO.md` 的正式产品待办。

### P0：直接提升 Agent 工程能力

1. `recommended`：增加实验性、有最大轮数/超时/Token 预算的 Agent Loop，保留当前
   Workflow 为稳定基线。
2. `recommended`：设计 Agent Run/Step、observation、stop reason、checkpoint 和 replay。
3. `recommended`：建立 tool precision/recall、task success、重复调用、越权调用、延迟和
   成本评测。

### P1：补齐生产 Agent 特征

1. `recommended`：建立动作提案、Policy、人工审批、短期授权、幂等执行和审计状态机。
2. `enhanced`：利用现有 diagnosis、trace、feedback 建立经审核的 episodic memory。
3. `recommended`：将依赖缺失、Runner 不可用、Docker Build 和权限失败等路径沉淀为 Skill。
4. `recommended`：实现只读 MCP Adapter 实验，验证工具发现、Schema、授权、租户上下文、
   超时和错误映射。

### P2：指标证明必要后再做

1. `recommended`：只对低置信度、证据冲突或高风险动作启用 Critic/Reflection。
2. `extension`：只有单 Agent 存在上下文隔离、并行调查或职责约束瓶颈时，再评估 Multi-Agent。

### 暂不优先

- 从头训练模型或深挖 RLHF/PPO/GRPO 实现。
- 复刻 OpenClaw 或同时引入多个 Agent 框架。
- 无评测地增加 Multi-Agent、聊天 UI 或新的向量数据库。
- 为“生产级”表述强行引入 Kubernetes。
- 自动修改代码或重跑 CI；写操作必须先完成授权和人工审批设计。

## 14. 分阶段学习产出

完整打勾清单见 [AI Agent 学习跟进清单](agent_learning_tracker.md)。四阶段目标如下：

1. **第 1—4 周**：手写有界 Agent Loop，掌握 Tool、Context、停止条件和失败恢复。
2. **第 5—8 周**：使用 LangGraph 对照实现 State、Checkpoint、Memory 和 HITL。
3. **第 9—12 周**：建立任务、轨迹、安全、成本和 Workflow/Agent 对比评测。
4. **第 13—16 周**：实现 Skill/MCP 实验、完成源码对照、项目材料和面试口述。

最终求职交付物应包括：现状与目标架构图、Workflow/Agent 选型 ADR、固定评测报告、轨迹
展示、3—5 分钟演示、30 秒/90 秒/5 分钟口述稿，以及明确的 `implemented/enhanced/
recommended/extension` 证据边界。
