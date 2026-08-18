# CI Assistant Platform Agent 化优化路线图

> 评估日期：2026-08-10
> 状态：P0、P1A/P1B 只提案模式已实现；其余 P1/P2 尚未批准
> 范围：只规划 `ci_assistant` 主包；`ci_analysis_demo` 不承接 Agent 新能力

## 1. 结论

当前系统是一个安全边界较完整的单轮 CI 诊断 Workflow，而不是可持续观察、决策和行动的
完整 Agent。它已经具备 Agent Harness 的重要底座：异步任务、Provider 抽象、只读 Tool、
租户 ACL、RAG、结构化输出、降级、Trace、反馈和离线评测。下一步不应继续堆叠 Prompt，
也不应直接引入 Multi-Agent；最有价值的增量是：

1. 在现有 Workflow 旁增加可关闭的、有预算上限的单 Agent Loop。
2. 把每轮决策、工具调用、Observation、预算和停止原因变成可回放状态。
3. 用固定评测证明 Agent Loop 相比现有 Workflow 的收益，再决定是否成为默认路径。
4. 在任何写操作之前建立 Policy、人工审批、幂等执行和审计状态机。

建议先做的最小范围是“只读 Agent Loop 实验模式”：复用现有 Provider Tool 和 RAG，最多
3 轮、最多 4 次工具调用、有总超时和上下文预算，不新增写工具，不自动评论、改代码或重跑
CI，Trace 暂存现有 `analysis_traces.trace_data`。

## 2. 从 Claude Code 提炼的工程能力

这里对照的是可迁移的 Agent 工程思想，不是复刻 Claude Code 的编码产品形态。

| Claude Code 能力 | 可迁移原则 | 本项目对应方向 |
| --- | --- | --- |
| Agentic turn 和 `--max-turns` | 自主循环必须有明确轮数与停止上限 | 最大轮数、工具数、总超时、Token/成本预算 |
| allow / ask / deny 与 Plan Mode | 权限应独立于模型判断，并采用 deny 优先 | Tool Policy、风险等级、审批门和默认只读模式 |
| Hooks | 确定性规则应由运行时强制，而不是只写在 Prompt | 调用前策略校验、结果脱敏、审计和越权阻断 |
| Session、resume、checkpoint | 长任务需要可恢复状态和明确恢复点 | Agent Run/Step、checkpoint、resume、replay |
| CLAUDE.md 与 Auto Memory | 常驻规则、按需知识和历史经验应分层 | 项目 Policy、Semantic/Episodic/Procedural Memory |
| Skills | 重复流程应版本化为按需加载的程序性知识 | CI 故障 Skill 注册、适用条件、版本和验收用例 |
| MCP | 外部工具接入应有统一发现和调用契约 | 只读 MCP Adapter，保留现有 Provider Protocol |
| Subagent 隔离上下文 | 高噪声、独立任务可隔离，主线程只接收摘要 | P2 才评估日志调查/变更调查专用子 Agent |
| Agent teams | 多 Agent 会显著增加成本和协调复杂度 | 仅在单 Agent 指标证明瓶颈后考虑 |

Claude Code 官方资料：

- [Claude Code overview](https://code.claude.com/docs/en/overview)
- [Configure permissions](https://code.claude.com/docs/en/permissions)
- [Hooks](https://code.claude.com/docs/en/hooks-guide)
- [Memory](https://code.claude.com/docs/en/memory)
- [Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Skills](https://code.claude.com/docs/en/skills)
- [MCP](https://docs.anthropic.com/en/docs/mcp)
- [Subagents](https://code.claude.com/docs/en/sub-agents)
- [Parallel agents](https://code.claude.com/docs/en/agents)

## 3. 当前项目能力基线

### 已具备

| 能力 | 代码证据 | 当前价值 |
| --- | --- | --- |
| 异步任务 Harness | `api/diagnoses.py`、`workers/diagnosis_tasks.py` | API 与耗时诊断解耦，支持重试和状态落库 |
| 单轮编排 | `diagnosis/orchestrator.py` | 串联日志预处理、RAG、Tool 和模型降级 |
| 结构化模型边界 | `llm/gateway.py`、`schemas/result.py` | 模型结果经 Pydantic 校验，失败可降级 |
| 只读工具策略 | `domain/tools.py`、`tools/executor.py` | enabled、read_only、allowlist、Capability 二次校验 |
| 多 CI Provider | `providers/` | GitLab、Jenkins、GitHub Actions 统一只读契约 |
| Semantic Memory | `knowledge/` | 租户 ACL、Hybrid、Reranker、真实引用 |
| Trace 与反馈 | `analysis_traces`、`diagnosis_feedback` | 已有诊断观测与用户反馈的数据基础 |
| 安全控制 | Secret Mask、Webhook 验签、租户鉴权 | 不可信输入隔离和租户边界已经形成 |

### 关键差距

| 差距 | 当前表现 | 影响 |
| --- | --- | --- |
| 无模型驱动 Agent Loop | 服务端预选工具后只调用模型一次 | 模型不能根据 Observation 再规划或补充证据 |
| 无统一 Agent State | 只有 Diagnosis 和结果级 Trace | 无法表达 goal、step、budget、checkpoint、stop reason |
| Trace 不足以回放 | 只记录耗时、引用数、工具名等摘要 | 无法还原每轮决策、参数、结果裁剪和失败恢复 |
| 无上下文预算器 | 日志有裁剪，但知识、Tool、轮次没有统一预算 | 多轮后容易超限、重复证据或成本失控 |
| 权限模型仍偏简单 | Tool 主要以 `read_only: bool` 区分 | 无法表达 ask/deny、作用域、风险级别和短期授权 |
| 无人工审批状态机 | 当前正确地完全禁止写操作 | 未来无法安全承接评论、Issue 或 CI 重跑 |
| 反馈尚未形成经验记忆 | 反馈只用于查询与汇总 | 不能从已审核的成功诊断中复用经验 |
| 无 Skill 生命周期 | 排障流程散落在规则、Prompt 和知识文档 | 缺少适用条件、版本、回归用例和发布治理 |
| 无 Agent 轨迹评测 | 主要评测结果与排序质量 | 无法证明更多轮次和工具调用确实提高任务成功率 |

## 4. 目标架构

```text
Diagnosis API / Webhook
        ↓
Diagnosis Worker
        ↓
Mode Router ─────────────→ Stable Workflow（现有默认路径）
        ↓ agent
Bounded Agent Runtime
  ├─ Agent State：goal / step / budget / stop reason
  ├─ Context Manager：日志、RAG、Observation 分层裁剪
  ├─ Planner：final_answer | tool_request | ask_approval
  ├─ Tool Policy：deny → ask → allow，租户与项目作用域
  ├─ Provider Tool / Read-only MCP Adapter
  ├─ Checkpoint + Resume + Replay
  └─ Trace + Metrics + Evaluation
        ↓
Structured Diagnosis Result
        ↓
可选 Action Proposal → Human Approval → Idempotent Executor
```

核心约束：

- `workflow` 始终保留为稳定基线和故障降级路径。
- Agent 每一轮只能返回 `tool_request`、`final_answer` 或 `ask_approval` 中的一种状态。
- Tool 调用前后都由运行时校验；Prompt 中的“禁止调用”不能代替权限系统。
- references 仍只能由检索层回填，模型不得生成来源。
- Agent Memory 写入必须经过租户隔离、脱敏、质量阈值和人工审核。
- 写操作必须经过提案、审批、幂等执行和审计，不与 P0 同时开放。

## 5. P0：可评测的只读 Agent Loop

目标：证明“根据 Observation 再规划”是否比当前 Workflow 更准确，而不是先追求自主程度。

实施状态：已完成。当前通过请求 `mode=agent` 与平台 `agent.enabled=true` 双重开关启用；
任一条件不满足都使用原 Workflow。P0 未新增数据库表、写工具、MCP 或 Multi-Agent。

### P0.1 运行模式与状态模型

- 增加内部 `workflow | agent` 模式开关，默认仍为 `workflow`。
- 定义内存态 `AgentRunState` 和 `AgentStep`：goal、round、status、tool request、observation
  摘要、预算消耗、stop reason、error code。
- P0 不新增数据库表，完整脱敏轨迹写入现有 `analysis_traces.trace_data`。
- 稳定停止原因至少包含：`completed`、`max_rounds`、`tool_budget_exhausted`、
  `timeout`、`repeated_call`、`policy_denied`、`model_error`、`fallback`。

### P0.2 有界循环

- 默认最多 3 轮、4 次工具调用、单次工具超时和任务总超时。
- 对相同工具名与规范化参数生成指纹，阻止无新信息的重复调用。
- 模型连续产生无效 Schema、空 Observation 或相同决策时立即停止并回退 Workflow。
- `DiagnosisGateway` 增加 Agent 决策契约，不改变现有最终结果契约。

### P0.3 上下文管理

- 分开管理 system policy、goal、日志证据、RAG、Tool Observation 和历史步骤。
- 为各分区配置字符/Token 预算；优先保留最近错误、真实引用和最新 Observation。
- Tool Result 先结构化裁剪、脱敏和标注来源，再进入模型上下文。
- 旧步骤只保留决策与 Observation 摘要，不重复拼接完整日志。

### P0.4 评测与可观测性

- 在固定 Case 中同时运行 Workflow 和 Agent，禁止只展示 Agent 最佳样例。
- 新增指标：task success、error type accuracy、tool precision/recall、无效工具率、重复调用率、
  policy deny rate、平均轮数、p95 延迟、fallback rate、输入/输出 Token 和单次成本。
- Agent 只有在质量提升达到预设阈值，且越权调用为零、延迟和成本在预算内时才允许扩大流量。

### P0 验收标准

- Agent Loop 的所有退出路径均有自动测试。
- 未注册、非只读、无 Capability、超预算和重复工具调用均被运行时阻止。
- 任意模型、RAG 或 Tool 异常都能得到稳定终态，不留下长期 `running` 记录。
- Trace 可以按 Step 顺序回放，但不包含 Secret、完整 CI 日志或完整知识正文。
- 默认 API 行为、Provider Protocol、知识索引格式和 Workflow 结果保持兼容。

## 6. P1：可恢复、可治理的 Agent Runtime

### P1.1 持久化与恢复

实施状态：P1A 已完成。Run/Step 使用追加式迁移；步骤以独立短事务形成恢复点，Replay
不返回内部续跑 Observation 上下文。

- 通过新增 Alembic revision 引入 `agent_runs`、`agent_steps` 或等价持久化模型。
- 为每步保存幂等键、输入摘要、决策、工具状态、预算、checkpoint 和 stop reason。
- Worker 重启后从最后一个已完成 Step 恢复；恢复前重新校验租户、Policy 和工具可用性。
- 提供只读 Trace/Replay API，不返回敏感 Observation 正文。

### P1.2 权限与 Human-in-the-loop

实施状态：P1B 只提案模式已完成。动作可以创建、批准、拒绝和审计，但没有执行器；即使
状态为 `approved` 也不会产生外部副作用。

- 将 `read_only: bool` 演进为 `effect=read|write`、`risk=low|medium|high`、作用域和
  `allow|ask|deny` Policy。
- 写动作先生成 `ActionProposal`，包含目标、参数摘要、风险、预期影响、过期时间和幂等键。
- 审批必须绑定租户、操作者、具体动作与参数；批准不能泛化为永久授权。
- 第一批写动作只选可撤销或低影响能力，例如创建草稿评论；CI 重跑和代码修改继续后置。

### P1.3 Memory 与 Skill

- Semantic Memory：继续使用当前知识库，不改变真实引用规则。
- Episodic Memory：只从高评分、建议被采纳、结果已验证的诊断中生成候选经验；经脱敏和
  审核后入库，并设置来源、租户、有效期和撤销能力。
- Procedural Memory：把依赖缺失、Runner 不可用、权限失败、Docker Build 等高频 SOP
  做成版本化 Skill，声明触发条件、所需工具、预算、输出 Schema 和固定回归 Case。
- Skill 只提供流程知识，不能绕过 Tool Policy。

### P1.4 MCP 实验

- 在现有 `ProviderToolExecutor` 外增加只读 MCP Adapter，不替换 `CIProvider`。
- 校验工具发现、JSON Schema、超时、错误映射、租户上下文透传和 Server allowlist。
- MCP 返回内容与原生 Tool 一样经过裁剪、脱敏和不可信标记。

## 7. P2：有指标依据的增强能力

- 仅对低置信度、证据冲突或高风险提案启用 Critic/Reflection，避免每次诊断固定增加一轮。
- 按任务复杂度路由模型：规则/小模型处理分类和摘要，强模型处理复杂规划与冲突消解。
- 单 Agent 出现明确的上下文污染或串行延迟瓶颈后，再实验调查型子 Agent；每个子 Agent
  使用独立上下文和最小工具集，主 Agent 只接收结构化摘要。
- 只有独立任务确实需要持续并行协作时才评估 Multi-Agent；必须同时评估 Token、延迟、
  冲突率和综合收益。
- 完成审批与沙箱后，逐步试点评论草稿、Issue 草稿和受控 CI 重跑；代码修改仍需独立设计。

## 8. 风险与控制

| 风险 | 触发方式 | 控制措施 |
| --- | --- | --- |
| 无限循环和成本失控 | 模型重复规划或反复调用工具 | 轮数、工具、Token、时间和成本硬预算；重复指纹阻断 |
| Prompt Injection | CI 日志、知识或 Tool 返回包含指令 | 不可信分区、结果脱敏、Tool Policy、运行时 deny 优先 |
| 越权与跨租户访问 | 模型构造其他项目或租户参数 | 服务端注入租户上下文，不接受模型提供 tenant ID |
| 错误记忆污染 | 未验证诊断自动写入经验库 | 反馈阈值、人工审核、来源追踪、版本和可撤销 |
| 恢复后重复副作用 | Worker 重试或 checkpoint 恢复 | Step 与动作幂等键、执行状态机、结果核对 |
| Trace 泄密 | 保存完整日志、Tool 返回或 Prompt | 只存摘要、Hash、结构化指标和受限错误字段 |
| Agent 比 Workflow 更差 | 更多轮次放大错误和延迟 | 固定 A/B 评测、Feature Flag、灰度和一键回退 |
| Multi-Agent 复杂度过早 | 为“更智能”直接并行多个 Agent | P2 门槛；先证明单 Agent 的具体瓶颈 |

## 9. 推荐实施顺序

### 最小接入范围（第一迭代）

1. 新增实验性 `agent` 模式，但默认关闭。
2. 定义 `AgentDecision`、`AgentRunState`、`AgentStep` 和停止原因枚举。
3. 复用现有三个 Provider 只读工具与 RAG，不增加 MCP 或写工具。
4. 实现最多 3 轮的 Agent Loop、重复调用阻断和统一上下文预算。
5. 将脱敏 Step 轨迹写入现有 AnalysisTrace。
6. 增加 10—20 个需要“一次补充证据后才能正确诊断”的固定 Case，与 Workflow 做对照。

这一步完成后再做决策：如果任务成功率和错误分类没有稳定提升，就保留 Workflow 默认路径，
只把 Agent 用于低置信度或证据不足的复杂 Case；如果有明确收益，再进入 P1 持久化与审批。

### 暂不纳入第一迭代

- LangGraph 或其他框架级重写。
- Multi-Agent、Agent Team 或通用聊天界面。
- 自动修改代码、自动合并、自动重跑 CI。
- 未经审核的自动 Memory 写入。
- 同时更换向量数据库、模型网关和 Tool 协议。

## 10. 交付物与决策门

| 阶段 | 必须交付 | 进入下一阶段的门槛 |
| --- | --- | --- |
| P0 设计 | 状态模型、循环协议、预算、Policy、评测集设计 | 人工确认公开兼容边界和测试范围 |
| P0 实现 | Feature Flag、只读 Loop、Trace、单元与固定评测 | 越权率 0；任务成功率有稳定收益；预算可控 |
| P1 设计 | 持久化、恢复、审批、Memory/Skill 治理 ADR | 安全与数据模型评审通过 |
| P1 实现 | Resume/Replay、审批状态机、审核式 Memory | 重试无重复副作用；审计完整；可回退 |
| P2 实验 | Critic、模型路由或子 Agent 对照报告 | 指标证明收益高于复杂度与成本 |

P0 已按本文边界实现；P1/P2 仍只定义建议和验收门，不代表已授权修改数据库、开放写操作、
MCP 或 Multi-Agent。正式优先级以 `docs/TODO.md` 为唯一入口，架构取舍记录在
`docs/DECISIONS.md`。
