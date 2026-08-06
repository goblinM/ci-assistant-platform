# AI Agent 学习跟进清单

本文用于跟进从“AI 诊断 Workflow”到“可评测、可恢复、安全受控 Agent”的学习和实践过程。
学习成果必须尽量映射到 `ci-assistant-platform`，但未经过独立设计评审的内容不得直接进入
主运行包。

## 使用方式

- 每周开始时只选择 3—5 个条目，避免同时铺开多个框架。
- 完成标准不是“看完”，而是能够口述、画图、写最小代码并回答取舍。
- 项目功能使用以下标签：`implemented` 已实现、`enhanced` 基于现状补强、
  `recommended` 后续建议、`extension` 项目未使用的扩展知识。
- 每阶段结束更新本文的日期、证据链接和复盘，不把计划项包装成已落地能力。

## 总目标

- [ ] 能从零实现有最大轮数、超时和预算限制的 Agent Loop。
- [ ] 能解释 Workflow、Agent、Tool、Skill、MCP、Memory 和 Harness 的边界。
- [ ] 能设计 Agent State、checkpoint、interrupt、resume 和幂等恢复。
- [ ] 能实现工具权限校验、人工审批和完整轨迹审计。
- [ ] 能用固定数据集评估任务成功率、工具选择、引用真实性、成本和安全性。
- [ ] 能用 30 秒、90 秒和 5 分钟三个版本介绍项目，并严格区分已实现与规划能力。

## 阶段一：Agent 基础与手写 Loop（第 1—4 周）

目标：不依赖 Agent 框架实现一个安全、有界、可测试的最小 Agent。

### 第 1 周：概念和现状基线

- [ ] 阅读 Hello-Agents 的 Agent 架构、ReAct、Tool Use 章节。
- [ ] 阅读 `learn-claude-code` 的最小 Agent Loop。
- [ ] 画出 `Goal → Decide → Act → Observe → Update State → Stop` 状态图。
- [ ] 对照 `DiagnosisOrchestrator` 画出当前项目真实调用链。
- [ ] 列出“当前 Workflow”和“目标 Agent Loop”的至少五个差异。
- [ ] 口述：为什么 Agent 不等于一次 LLM + RAG + Tool 调用。

验收证据：

- [ ] 一张现状与目标架构对比图。
- [ ] 一份 10 分钟口述录音或文字稿。
- [ ] 能明确说明当前项目没有模型驱动的多轮 ReAct。

### 第 2 周：Tool Calling 与执行边界

- [ ] 理解 Function Calling 中“模型决策、宿主执行”的职责分离。
- [ ] 阅读 `ProviderToolExecutor` 的候选筛选和执行二次校验。
- [ ] 掌握 JSON Schema、参数校验、未知工具拒绝和结果裁剪。
- [ ] 设计最大调用次数、重复调用检测、单工具超时和总截止时间。
- [ ] 为最小 Agent 编写正常调用、非法调用、超时和重复调用测试。
- [ ] 口述 Function Calling、Tool、Skill 和 MCP 的区别。

验收证据：

- [ ] 最小 Agent 至少有三个只读工具。
- [ ] 非法工具和越权参数能被宿主拒绝。
- [ ] 单个工具失败不会导致无限循环。

### 第 3 周：上下文工程

- [ ] 阅读 `learn-claude-code` 的 context、todo/task 和 compact 相关阶段。
- [ ] 区分 system instruction、用户输入、工具结果和检索证据。
- [ ] 设计 observation 的脱敏、裁剪、摘要和引用策略。
- [ ] 理解 context window、输入 Token、Prompt Cache 和信息损失的取舍。
- [ ] 为长 CI 日志设计“关键片段 + 原始位置 + 摘要”的上下文格式。

验收证据：

- [ ] 构造一个超长日志 Case，Agent 能在预算内完成任务。
- [ ] 压缩前后结论和关键证据可对比。
- [ ] Prompt 中不可信日志和工具结果具有明确边界。

### 第 4 周：停止条件和失败恢复

- [ ] 实现 `final_answer`、最大步数、总超时、预算耗尽四类停止条件。
- [ ] 实现重复工具调用或无进展检测。
- [ ] 区分可重试错误、不可重试错误和业务失败。
- [ ] 对模型返回空内容、非法 JSON 和不存在工具编写测试。
- [ ] 完成阶段复盘：框架替你隐藏了哪些机制。

验收证据：

- [ ] 所有失败路径都有稳定 stop reason。
- [ ] 不会因为模型持续请求同一工具而无限运行。
- [ ] 能解释 retry、fallback 和重新规划的区别。

## 阶段二：状态、记忆与 HITL（第 5—8 周）

目标：理解持久化 Agent Runtime，并完成可暂停、可恢复的实验实现。

### 第 5 周：LangChain 与 LangGraph 基础

- [ ] 学习 LangChain Message、Tool、Structured Output 和 `create_agent`。
- [ ] 学习 LangGraph State、Node、Edge 和 Conditional Edge。
- [ ] 用 LangGraph 重写阶段一最小 Agent，保持相同测试 Case。
- [ ] 比较手写 Loop 与 LangGraph 的状态、错误和测试边界。
- [ ] 记录哪些能力值得引入，哪些会增加不必要依赖。

### 第 6 周：Persistence、Checkpoint 与 Resume

- [ ] 理解 thread、checkpoint、run 和 step 的区别。
- [ ] 实现运行中断后的恢复。
- [ ] 验证工具已经成功但状态写入失败时的幂等策略。
- [ ] 设计 `agent_runs`、`agent_steps` 的概念模型，不立即修改生产数据库。
- [ ] 为 crash/restart 场景编写测试。

### 第 7 周：Memory 分层

- [ ] 区分 short-term、semantic、episodic、procedural memory。
- [ ] 阅读 nanobot 的 session/memory 实现。
- [ ] 阅读 Hermes Persistent Memory 和写入审批机制。
- [ ] 设计“诊断 + 用户反馈 → 候选经验 → 审核 → 长期知识”的链路。
- [ ] 定义记忆污染、过期、冲突、租户隔离和删除策略。

验收证据：

- [ ] 不把完整历史对话直接等同于长期记忆。
- [ ] 能说明何时检索历史诊断，何时检索团队知识。
- [ ] 未经确认的模型总结不会直接进入长期知识。

### 第 8 周：Human-in-the-loop

- [ ] 学习 LangGraph interrupt/resume 或等价机制。
- [ ] 设计动作提案、审批、短期授权、执行和审计状态机。
- [ ] 为批准、拒绝、超时、重复审批编写测试。
- [ ] 设计 PR 评论草稿或 Pipeline 重跑建议，不执行真实外部写操作。
- [ ] 明确审批不能替代后端权限校验。

## 阶段三：Agent 评测（第 9—12 周）

目标：从“能跑”提升到“能够证明改进有效”。

### 第 9 周：任务和轨迹数据集

- [ ] 为依赖缺失、Runner 不可用、权限失败、测试失败建立固定 Case。
- [ ] 每个 Case 标注期望错误类型、允许工具、禁止工具和最大步骤。
- [ ] 标注必须引用的知识以及不可声称的结论。
- [ ] 为正常、边界和对抗输入分别准备样例。

### 第 10 周：核心指标

- [ ] 实现 task success rate。
- [ ] 实现 tool precision/recall。
- [ ] 实现 prohibited tool call rate。
- [ ] 实现平均步骤数、重复调用率和 fallback rate。
- [ ] 记录延迟 p50/p95 和单任务 Token/成本。
- [ ] 继续使用 Recall@K、MRR 和引用精度评估 RAG。

### 第 11 周：安全与对抗评测

- [ ] 测试日志中的 Prompt Injection。
- [ ] 测试工具结果中的恶意指令。
- [ ] 测试跨租户检索和跨项目工具调用。
- [ ] 测试敏感参数进入 trace、日志和模型上下文的情况。
- [ ] 测试模型请求写工具、未知工具和超预算工具调用。

### 第 12 周：基线对比

- [ ] 对比当前确定性 Workflow 和实验 Agent Loop。
- [ ] 比较准确率、工具选择、延迟、成本和失败率。
- [ ] 定义 Agent 模式值得启用的适用条件。
- [ ] 如果 Agent 没有显著收益，如实保留 Workflow 作为默认方案。
- [ ] 输出一份可复现评测报告。

## 阶段四：项目化和求职表达（第 13—16 周）

### 第 13 周：Skill 与 MCP

- [ ] 定义“Python 依赖缺失排障”Skill。
- [ ] 定义“Runner 不可用排障”Skill。
- [ ] 每个 Skill 包含触发条件、工具、步骤、停止条件、风险和评测 Case。
- [ ] 阅读 MCP Host、Client、Server、Tool 和 Resource 的基本协议。
- [ ] 实现一个只读 MCP 实验 Adapter，不直接替换主平台工具层。

### 第 14 周：源码对照学习

- [ ] 精读 nanobot Agent Loop、Tool Registry、Session 和 Memory。
- [ ] 选读 OpenClaw Runtime、Tool Policy、Skill 和 Plugin。
- [ ] 选读 Hermes Memory、Session Search 和 Skill 写入审批。
- [ ] 每个项目只总结三项可迁移设计和三项不适合本项目的设计。

### 第 15 周：项目材料

- [ ] 更新架构图，区分现行架构和实验 Agent 架构。
- [ ] 编写 Workflow 与 Agent 选型 ADR。
- [ ] 准备 3—5 分钟演示视频。
- [ ] 准备固定评测结果截图或报告。
- [ ] 更新 README、架构、评测和安全边界说明。

### 第 16 周：面试训练

- [ ] 完成 30 秒项目定位。
- [ ] 完成 90 秒项目介绍。
- [ ] 完成 5 分钟架构、取舍、失败模式和评测介绍。
- [ ] 回答“为什么不用/为什么使用 LangGraph”。
- [ ] 回答“为什么不直接做 Multi-Agent”。
- [ ] 回答“Agent 如何避免乱调工具和无限循环”。
- [ ] 回答“Memory 如何避免污染和跨租户泄露”。
- [ ] 回答“如何证明 Agent 比 Workflow 更好”。

## 项目改进候选池

以下条目只是学习和设计候选，不代表已经批准进入产品待办。

### P0

- [ ] `recommended`：有界 Agent Loop 实验模式。
- [ ] `recommended`：Agent Run/Step 轨迹模型与回放设计。
- [ ] `recommended`：工具选择、任务成功率和安全评测。

### P1

- [ ] `recommended`：Human-in-the-loop 动作提案与审批状态机。
- [ ] `enhanced`：基于 diagnosis、trace、feedback 的 episodic memory。
- [ ] `recommended`：CI 排障 Skill 注册和版本管理。
- [ ] `recommended`：只读 MCP Adapter 实验。

### P2

- [ ] `recommended`：仅对低置信度或证据冲突结果启用 Critic。
- [ ] `extension`：单 Agent 指标证明存在瓶颈后再评估 Multi-Agent。

## 每周复盘模板

```markdown
### YYYY-MM-DD｜第 N 周

- 本周目标：
- 完成条目：
- 代码/文档证据：
- 我现在能独立解释：
- 仍然不理解：
- 实验结果：
- 对 ci-assistant-platform 的影响：
- 证据等级：implemented / enhanced / recommended / extension
- 下周只做的三件事：
```

## 学习资料顺序

1. Hello-Agents：建立 Agent 知识地图。
2. learn-claude-code：理解 Agent Loop 和 Harness。
3. 手写最小 Agent：验证自己是否真正理解。
4. LangChain/LangGraph：学习状态、持久化和 HITL。
5. nanobot：精读较小的完整 Agent Runtime。
6. 小林 Coding：按 Agent、Tool、RAG、LangGraph 专题复盘。
7. Hermes Agent：学习持久记忆和受控经验写入。
8. OpenClaw：选读 Runtime、Tool Policy、Skill、Plugin 和多 Agent routing。
9. AgentGuide、ai-agent-interview-guide、Agent-Learning-Hub：查漏补缺，不作为主线教材。

## 面试表达红线

- [ ] 不把确定性 Workflow 说成完整 ReAct。
- [ ] 不把知识库说成完整 Agent Memory。
- [ ] 不把诊断级 trace 说成可恢复 Agent trajectory。
- [ ] 不把文档中的 MCP 设计说成已经实现。
- [ ] 不把规划中的审批写操作说成已经上线。
- [ ] 不虚构生产流量、准确率、成本下降或个人 ownership。
