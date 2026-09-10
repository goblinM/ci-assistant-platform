# 工程决策记录

## ADR-001：主包与发行名

- 状态：已接受
- 决策：Python 主包使用 `ci_assistant`，发行名使用 `ci-assistant-platform`。
- 兼容：`ci_analysis_demo` 仅作为旧 API 兼容包。
- 原因：避免新旧模块继续交叉依赖，并保持调用方渐进迁移能力。

## ADR-002：持久化职责拆分

- 状态：已接受
- 决策：PostgreSQL 保存业务和知识元数据，Redis 保存 Celery 队列与短期结果，FAISS
  保存版本化向量索引。
- 原因：知识正文需要事务与审计；队列需要短期、高吞吐状态；向量检索需要独立索引。
- 恢复：PostgreSQL 是业务恢复基线，FAISS 可由知识 Chunk 重建。

## ADR-003：统一 CI Provider

- 状态：已接受
- 决策：诊断编排只依赖 `CIProvider`，GitLab/Jenkins/GitHub 原始响应限制在 Adapter 内部。
- 原因：统一 Run、Job、Log、Change 和 Webhook 语义，避免业务层绑定单一 CI。

## ADR-004：默认只读和真实引用

- 状态：已接受
- 决策：自动 Tool 默认只读；references 只能来自带 ACL 的真实检索结果。
- 原因：CI 日志和知识均是不可信输入，自动写操作和模型自造引用风险不可接受。

## ADR-005：依赖真源

- 状态：已接受
- 决策：`pyproject.toml` 是项目依赖真源；容器清单和兼容 requirements 由自动测试约束
  名称集合一致。
- 原因：避免本地、容器和兼容安装得到不同的目标运行环境。

## ADR-006：ADOS 渐进治理

- 状态：已接受
- 决策：治理按 P0/P1/P2 渐进实施，不批量重构历史代码；只对实际触及的公共接口补充
  Docstring 和测试。
- 原因：减少治理噪声，保持公开行为和兼容链路稳定。

## ADR-007：Agent P0 采用旁路、有界、默认关闭的只读循环

- 状态：已接受。
- 决策：保留现有 Workflow 为默认路径，只在请求选择 `agent` 且平台显式启用时运行最多
  3 轮的只读 Agent Loop；停止或异常时回退 Workflow。
- 状态：P0 使用内存态 Run/Step，并将脱敏轨迹写入现有 `analysis_traces.trace_data`，不新增
  数据库表。
- 权限：模型只选工具名，资源参数由服务端注入；候选筛选、Capability 与只读校验不可绕过。
- 原因：先用固定评测证明多轮决策收益，同时限制成本、越权、循环和兼容风险。
- 后续：持久化恢复、审批、Memory、Skill、MCP 和 Multi-Agent 必须分别进入 P1/P2 评审。

## ADR-008：Agent P1A/P1B 采用可恢复检查点与只提案审批

- 状态：已接受。
- 决策：Agent Run/Step 使用追加式迁移持久化；每个完成步骤在独立短事务提交，Worker 重试
  从最后检查点恢复预算、调用指纹和脱敏受限上下文。
- 回放：租户级 Replay API 不返回内部 Observation 正文，只返回步骤、摘要和 Hash。
- 权限：Tool Policy 使用 `effect`、`risk`、`allow|ask|deny`；只有只读且 allow 的工具可执行。
- 提案：人工批准和拒绝形成不可变审计事件，但 P1 不提供动作执行器，批准不产生外部副作用。
- 延后：自动 Memory、Skill、MCP、写工具和 Multi-Agent 继续单独评审。

## ADR-009：Agent 可靠性采用提交后派发、数据库认领与结果快照

- 状态：已接受。
- 派发：Diagnosis 在数据库提交成功后才发送 Celery 任务，避免消费早于数据可见。
- 认领：Worker 使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 串行化同一诊断，事务失败时锁和
  状态一起回滚。
- 幂等：Agent Run/Step 使用唯一约束与 Savepoint 处理并发插入；同序号不同内容视为冲突。
- 恢复：最终结构化答案先写入 Agent Run 快照，再与 Diagnosis 结果提交；重试直接复用快照。
- 审批：Proposal 在行锁内完成一次决策，过期状态通过可提交的 409 响应持久化。
- 边界：不增加写工具、动作执行器、Memory、MCP 或 Multi-Agent。

## ADR-010：Agent 推理增强采用证据缺口、分区上下文与按需单次自检

- 状态：已接受。
- 上下文：日志、知识、最新 Observation 和旧 Observation 使用独立预算，最新 Observation
  优先保留，总字符和估算 Token 硬预算保持不变。
- 工具：模型可见完整 JSON Schema，但只选择工具名并说明证据缺口；项目、租户和运行参数
  继续由服务端注入，Schema 禁止附加参数。
- 自检：仅在低置信度或稳定状态证据冲突时增加一次自检，并受既有最大轮数和总预算约束。
- 评测：A/B Harness 必须实际调用同批 Case 的 Workflow/Agent Runner，不接受静态样例冒充
  真实运行指标。
- 审计：工具证据缺口随 Step 持久化并进入租户级只读 Replay；Prometheus 只使用固定工具名、
  结果和自检触发标签，未知工具统一归类，禁止把模型文本放入标签。
- 适配：编排输出通过无日志适配器进入 A/B Harness，不读取完整 Prompt 或 Observation 正文。
- 边界：不引入独立 Critic、Memory、MCP、写工具或 Multi-Agent。
