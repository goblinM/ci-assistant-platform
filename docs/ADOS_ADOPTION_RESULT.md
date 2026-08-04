# CI Assistant Platform ADOS 接入结果

> 执行日期：2026-07-27
> 接入范围：用户确认的 P0 项目  
> 项目：`ci-assistant-platform`

## 执行边界

本次只实施已确认的最小治理接入：

- 建立项目级 AI 协作约束。
- 校准 README 和现有架构说明。
- 建立安全、可回滚的 Git 初始基线。
- 收紧 PostgreSQL 本地端口和默认密码策略。

目录结构、业务代码、公开 API、数据库 Schema、依赖和 CI/CD 均未调整；未进行批量重构。

## 实际修改

| 文件或操作 | 结果 |
| --- | --- |
| `AGENTS.md` | 新增 ADOS 引用、主包/兼容包边界、安全约束和验证要求 |
| `README.md` | 架构图更新为 FastAPI、Celery、Provider、PostgreSQL、Redis、FAISS 实际链路 |
| `docs/architecture.md` | 保留原文件位置，更新为 0.5.0 实际组件、数据流、边界和兼容策略 |
| `docs/platform_operations.md` | 补充数据库必填密码、本机端口和已有数据卷密码变更提示 |
| `docker-compose.yml` | PostgreSQL 改为 `127.0.0.1` 绑定；缺少密码时明确失败 |
| `.env.example` | 增加 `POSTGRES_PASSWORD`、`POSTGRES_PORT` 和一致的本地数据库 URL |
| `.gitignore` | 忽略 `.env.*` 与 IDE 目录，同时显式保留 `.env.example` |
| Git 初始基线 | 提交 `757598e`：`chore: establish initial project baseline` |

## 安全复核

- `.env` 未进入 Git 基线。
- `venv`、缓存、egg-info、IDE 工作区和数据目录未进入 Git 基线。
- PostgreSQL 本地调试端口不再监听全部主机接口。
- Compose 不再使用 `ci_assistant` 作为数据库默认密码回退值。
- 已有 PostgreSQL 数据卷的角色密码不会由环境变量自动更新，运维文档已明确提示。

## 最小必要验证

实际执行：

```text
venv/bin/pytest -q ci_assistant/tests/test_compose.py ci_assistant/tests/test_config.py
```

结果：`8 passed in 0.13s`。

同时执行：

```text
POSTGRES_PASSWORD=ados-config-validation docker-compose config --quiet
git diff --check
```

结果：Compose 配置解析通过，Git 差异格式检查通过。

没有启动应用、数据库、Worker 或外部 Provider；没有执行完整测试集。

## ADOS 验证

实际运行 ADOS `validate_adoption.py`，机器结果为 `Failed`。

通过项：

- `AGENTS.md`、README 和架构文档存在且非空。
- `AGENTS.md` 已引用 ADOS。
- 项目名称、运行命令和测试命令可识别。
- 未发现危险的目录调整记录。

失败项：

- 缺少 `docs/DEVELOPMENT.md`。
- 缺少 `docs/TODO.md`。
- 缺少 `docs/DECISIONS.md`。
- 缺少 `docs/DEBUG.md`。
- 缺少 `docs/CHANGELOG.md`。

这些文件未包含在本次确认的 P0 清单中，因此没有为迎合验证器额外创建。现有同类事实继续
由 `docs/architecture.md`、`docs/DECISIONS.md`、`docs/TODO.md`、
`docs/platform_operations.md` 和现有验收材料承载。结论是：已确认 P0 范围实施和专项测试
通过，但完整 ADOS 文档矩阵验证未通过。

## 后续边界

P0 完成时，P1/P2 尚未执行；后续治理继续以 `757598e` 为接入前基线审查差异。

## P1 治理结果

> 执行日期：2026-07-27
> 基线：`55aee2e`

### 实施内容

- 新增 Worker 安全失败日志，只记录任务名、业务标识、稳定错误码和异常类型，不记录异常
  正文、Prompt 或 CI 日志。
- 新增 `KNOWLEDGE_INGESTION_FAILED` 稳定错误码。
- 为本次实际修改的诊断、知识入库和重建任务入口补充中文 Docstring。
- 明确 `pyproject.toml` 为依赖真源，使 `requirements.txt` 与
  `requirements-runtime.txt` 保持目标运行依赖一致；pandas 和 SentenceTransformer 继续只
  属于 `legacy` 可选依赖。
- 将 `docs/evaluation.md` 更新为单元、契约、持久化、知识、安全、Compose E2E 和外部
  Provider 七层测试矩阵。
- 在架构文档中补充兼容包退役的五项必要条件。

没有批量补历史 Docstring，没有拆分 `ci_analysis_demo/services/llm_service.py`，没有移动
目录、修改公开 API、数据库 Schema、依赖版本或 CI/CD。

### 验证结果

专项测试：

```text
venv/bin/pytest -q \
  ci_assistant/tests/test_task_logging.py \
  ci_assistant/tests/test_dependency_governance.py \
  ci_assistant/tests/test_workers.py
```

结果：`3 passed in 0.21s`。

完整回归：

```text
venv/bin/pytest -q
```

结果：`60 passed, 1 warning in 7.82s`。唯一警告来自 FastAPI TestClient 对当前 Starlette
适配层的弃用提示，不是本次治理引入的失败。

`compileall` 与 `git diff --check` 均通过。未启动 Compose 或调用外部 GitLab、Jenkins、
LLM 服务。

### 未纳入本次 P1

- 255 个静态扫描 Docstring 缺口只采用“触及时治理”，未批量修改。
- 750 行兼容层 LLM 文件需在退役或真实功能需求中单独评审。
- CI/CD、ADR、依赖锁定和兼容包实际删除仍属于后续治理。
- ADOS 验证器要求的五份额外文档仍未获授权创建，机器验证状态保持 `Failed`。

## P2 治理结果

> 执行日期：2026-07-27
> 基线：`5206738`

### 实施内容

- 新增 GitHub Actions `Quality` 工作流，在 Python 3.10/3.11 执行安装、完整测试、源码编译
  和 Alembic 离线升级 SQL 校验，权限限制为 `contents: read`。
- 新增 ADOS 轻量文档入口：开发、待办、决策、排障和 Changelog；已有长文档继续保留并由
  入口引用。
- 记录主包命名、持久化职责、Provider、默认只读、依赖真源和渐进治理六项工程决策。
- 补充 PostgreSQL 逻辑备份、FAISS 重建、隔离恢复演练和危险恢复命令边界。
- 新增 CI 质量门和 ADOS 文档存在性自动测试。

没有升级或锁定依赖，没有删除兼容包，没有修改公开 API、数据库 Schema 或业务目录，也没有
启动外部服务。

### 验证结果

- P2 专项测试：`5 passed in 0.30s`。
- GitHub Actions YAML 静态解析：通过。
- `alembic upgrade head --sql`：两个 revision 均成功生成 PostgreSQL SQL。
- 完整回归：`62 passed, 1 warning in 8.76s`。
- `compileall` 与 `git diff --check`：通过。
- ADOS `validate_adoption.py`：`Passed`，13 项检查全部通过，无 warning、无 failure。

GitHub Actions 文件已在本地验证，但远端工作流是否成功仍需提交推送后由 GitHub 实际运行，
本次不把未发生的远端执行声明为通过。

### 后续治理

- 观察首次 GitHub Actions 运行并修复环境特有问题。
- 根据实际发布需求选择依赖锁定、SBOM 和镜像漏洞扫描方案。
- 定期执行 PostgreSQL 恢复演练并记录 RPO/RTO。
- 兼容包必须满足架构文档的五项门槛后再进入独立退役变更。

## P1 Docstring 专项治理结果

> 执行日期：2026-07-28
> 基线：`db5f38f`

用户确认将原“触及时治理”调整为一次性专项治理后，重新运行 ADOS 静态扫描。受 P2
新增治理测试影响，实时缺口由历史记录的 255 处变为 256 处，分布在 96 个 Python 文件：
`ci_assistant` 198 处、`ci_analysis_demo` 58 处。

本次仅为扫描命中的公共函数补充中文 Docstring，没有修改函数签名、控制流、公开 API、
Provider Protocol、数据库迁移逻辑或知识索引格式。治理后重新扫描，公共函数 Docstring
缺口为 0。

为防止批量修改引入行为变化，对全部 96 个涉及文件执行治理前后 AST 对比；比较时仅移除
模块、类和函数的 Docstring 节点，其余结构必须完全一致。结果为 96 个文件全部一致，
Docstring 之外的 AST 变化为 0。

验证结果：

- `python3 -m compileall -q ci_assistant ci_analysis_demo`：通过。
- `venv/bin/pytest -q`：`62 passed, 1 warning in 5.66s`。
- ADOS 静态扫描：`missing_public_docstrings = 0`。
- `git diff --check`：通过。

唯一警告仍为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示，与本次 Docstring
治理无关。未启动应用、数据库、Worker 或外部 Provider。

## 0.6.0 GitHub Actions Provider

> 执行日期：2026-07-28
> 基线：`36fd1c1`

### 实施内容

- 新增只读 GitHub Actions Client 和 Provider，覆盖 Workflow Run、Job、Job Log 与
  Head Commit。
- 将 GitHub 状态和结论映射到现有统一 `RunStatus`，没有修改 `CIProvider` Protocol。
- 支持 `workflow_run` 和 `workflow_job` Webhook；使用原始请求体校验
  `X-Hub-Signature-256` HMAC-SHA256。
- 将 Run Attempt、Action 和对象 ID 纳入外部事件标识，保持重投幂等并区分重跑。
- 配置和 Provider Manager 增加 `github` 类型；推荐注入短期 GitHub App Installation
  Token。
- 知识文档 Provider ACL 增加 `github` 枚举值，复用现有 PostgreSQL 和 FAISS 过滤结构。
- 版本更新为 0.6.0，并同步 README、架构、安全、API 示例和开发跟踪文档。

本次没有新增依赖、数据库迁移或写操作，没有修改公开诊断 API、知识索引格式和旧兼容包。
没有实现 Workflow 重跑、取消、评论或 Check 写入。

### 验证结果

- GitHub/Provider/配置/安全专项测试：`18 passed, 1 warning in 0.98s`。
- 完整回归：`69 passed, 1 warning in 5.57s`。
- `python3 -m compileall -q ci_assistant ci_analysis_demo`：通过。
- ADOS 静态扫描：`missing_public_docstrings = 0`。
- ADOS `validate_adoption.py`：`Passed`，无 warning、无 failure。
- `git diff --check`：通过。

唯一警告仍为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。验证使用 Mock
Provider 数据，没有连接真实 GitHub 或触发外部 Workflow。

## 0.6.1 多格式知识解析

> 执行日期：2026-07-28
> 基线：`fee34ac`

### 实施内容

- 新增 `POST /api/v1/knowledge/documents/files`，支持 PDF、DOCX 和 HTML 文件上传，并复用
  现有租户鉴权、版本、去重、Secret Mask、Chunk、Provider ACL 和索引任务。
- HTML 使用标准库提取标题和正文，忽略 script、style 和 noscript，不加载外部资源。
- DOCX 使用标准库 ZIP/XML 解析，限制成员数、解压后大小和压缩比。
- PDF 使用 PyMuPDF 在文件大小、页数、DPI 和总像素约束内渲染为 PNG，再调用独立
  Unlimited-OCR OpenAI-compatible 服务。
- Unlimited-OCR 默认关闭；未配置或服务不可用时返回稳定
  `SERVICE_UNAVAILABLE`，不把模型、Torch、CUDA 或动态远程代码放入 API/Worker。
- 版本更新为 0.6.1，并同步依赖真源、运行依赖、配置、架构、安全、API 和运维文档。

没有新增数据库迁移，没有改变已有 Markdown/JSON API、知识索引格式或公开诊断 API。

### 验证结果

- 文档解析/上传/配置/依赖专项测试：`25 passed, 1 warning in 0.78s`。
- 完整回归：`83 passed, 1 warning in 8.25s`。
- PyMuPDF 渲染页数和像素限制通过可控模块替身验证。
- Unlimited-OCR 多图片 OpenAI-compatible 请求和响应通过 MockTransport 验证。
- `python3 -m compileall -q ci_assistant ci_analysis_demo`：通过。
- ADOS 静态扫描：`missing_public_docstrings = 0`。
- ADOS `validate_adoption.py`：`Passed`，无 warning、无 failure。
- `git diff --check`：通过。

本机没有安装 PyMuPDF，也没有可用的 Unlimited-OCR GPU 服务。尝试安装 PyMuPDF 时外部
下载未获授权，因此没有执行真实 PDF 渲染或 PDF→Unlimited-OCR 端到端验收；部署前仍需在
获准环境中安装锁定依赖、启动固定版本 GPU 服务并使用非敏感 PDF Fixture 验收。唯一测试
警告仍为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。

## PROJECT_ONBOARDING 补齐

> 执行日期：2026-07-28

- 新增 `docs/PROJECT_ONBOARDING.md`，基于当前 FastAPI、Celery、Provider、Webhook
  投递审计、PostgreSQL、Redis、知识解析和 FAISS 真实链路提供快速接手入口。
- 增量更新 `AGENTS.md`，加入 Onboarding、开发、待办、工程决策、排障和 Changelog
  文档导航；保留原有主包、兼容包、安全和验证约束。
- 未移动目录，未修改业务代码、公开 API、依赖、数据库结构或 CI/CD。
- ADOS `validate_adoption.py` 验证结果为 `Passed`，14 项检查通过；`git diff --check`
  通过。

## 0.6.2 Cross-Encoder/BGE Reranker

> 执行日期：2026-07-29

### 实施内容

- 新增 `disabled | local | http` Cross-Encoder/BGE Reranker。`local` 使用可选
  SentenceTransformers 依赖并在 Worker 进程内懒加载、缓存模型；`http` 复用独立
  `/rerank` 服务。
- 启用后按配置扩大 Hybrid 候选集；HTTP 后端兼容 `results/relevance_score` 与
  `data/score`，本地后端在线程中执行 `CrossEncoder.predict`。
- 两种后端统一校验候选映射和有限数值分数，保留原 `hybrid_score`；依赖缺失、模型加载、
  推理、网络、超时、HTTP 或非法响应均降级到原 Hybrid 排序。
- 版本更新为 0.6.2，并同步配置模板、README、架构、安全、运维、RAG、Onboarding、
  Changelog、TODO 和开发跟踪文档。

没有修改公开诊断 API、Provider Protocol、数据库结构或知识索引格式，没有安装
SentenceTransformers，也没有启动外部 Reranker 服务。

### 验证结果

- Reranker、配置、Hybrid、Worker、版本和依赖专项测试：`24 passed`。
- 完整回归：`98 passed, 1 warning in 7.62s`。
- `python -m compileall -q ci_assistant ci_analysis_demo`：通过。
- ADOS 静态扫描：`missing_public_docstrings = 0`，无 Python 解析错误。
- ADOS `validate_adoption.py`：`Passed`，14 项检查全部通过。
- `git diff --check`：通过。

唯一警告仍为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。HTTP 请求通过
`httpx.MockTransport` 验证，本地 CrossEncoder 使用确定性模型替身验证了线程推理、排序、
进程内缓存、依赖缺失降级和后端工厂。由于没有安装真实 SentenceTransformers 模型，也没有
配置外部 BGE 服务，本次未执行真实模型排序质量和性能验收；后续需使用固定评测集比较
Recall@k、MRR、延迟、内存/显存和降级率。

## 0.6.2 排序评测、反馈闭环与 Embedding cache

> 执行日期：2026-07-29

### 实施内容

- 新增主平台固定离线排序评测，比较 Hybrid 与 Reranker 的 Recall@1/3、MRR、Metadata
  hit rate 和 Reference precision；评测不加载外部模型或访问网络。
- 新增租户隔离的诊断反馈写入、单条查询和汇总接口。反馈按诊断幂等更新，评论写入前执行
  Secret Mask，不自动触发训练、知识入库或 CI 写操作。
- 新增 `diagnosis_feedback` 表及追加式 Alembic revision `20260729_0004`，保留历史迁移。
- 新增本地 SQLite embedding cache，cache key 包含模型参数和文本 SHA-256，不保存原文；
  支持批量命中、容量回收及数据库故障降级。

没有修改公开诊断 API、Provider Protocol 或知识索引格式，没有连接真实 Provider、外部
Reranker 或模型服务。

### 验证结果

- 新增功能与相关回归：`17 passed, 1 warning`；完整回归：`108 passed, 1 warning`。
- 离线排序基线：Hybrid/Reranker Recall@1 为 `0.333/1.0`，MRR 为 `0.611/1.0`。
- Alembic 离线 SQL 和真实 Compose PostgreSQL 均到达 `20260729_0004`，
  `diagnosis_feedback` 表存在。
- 更新后的 API/Worker 容器启动成功；ready 中 PostgreSQL、Redis 均为 `ok`，OpenAPI
  包含反馈写入/查询与汇总路由。
- ADOS 静态扫描 `missing_public_docstrings = 0`；`validate_adoption.py` 为 `Passed`，
  14 项检查通过；`git diff --check` 通过。

唯一测试警告为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。本次离线排序数据为
确定性契约样例，不能代表真实 BGE 模型质量；后续仍需使用固定模型 revision 和脱敏知识集
建立质量、延迟及资源基线。

## P0 文档去重

> 执行日期：2026-07-30

### 实施内容

- 将当前架构、开发验证、待办、变更和工程决策继续收敛到现有 ADOS 核心文档。
- 校准 `architecture.md` 的 0.6.2 版本描述，更新 README、AGENTS、Onboarding 和 MVP
  文档导航。
- 删除已被现行文档替代的产品化分析、开发设计、开发跟进和产品化设计四份历史文档。
- 未新增文档、未移动目录，未修改业务代码、公开 API、依赖、数据库、迁移或 CI/CD。

### 验证结果

- ADOS `validate_adoption.py`：`Passed`，14 项检查通过，无 warning 或 failure。
- 已删除文件名的 Markdown 残留引用检查：无匹配。
- `git diff --check`：通过。
- 未运行项目测试、编译或服务；本次仅修改文档。

## P1 核心 Docstring 治理

> 执行日期：2026-08-04

### 实施内容

- 为诊断编排、Webhook、知识服务、Provider 管理、索引、检索、模型网关和只读 Tool
  执行器补充准确中文类 Docstring。
- 替换目标文件中“执行对应操作”等占位描述，说明真实顺序、权限、幂等、降级和副作用。
- 校准 `orchestrator.py` 的日志脱敏及不可信 Prompt 分区注释；保留用户已有代码逻辑。
- 未修改函数签名、公开 API、依赖、数据库、迁移、CI/CD 或兼容包。

### 验证结果

- ADOS 静态扫描：10 个目标文件的缺失类 Docstring 和 Docstring warning 均归零。
- `venv/bin/python -m compileall -q ci_assistant ci_analysis_demo`：通过。
- `venv/bin/pytest -q`：`108 passed, 1 warning in 8.69s`。
- 唯一 warning 为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。

### 第二批：公开契约与配置边界

- 为租户鉴权、请求 ID、HTTP 指标、平台配置、稳定错误码、CI 领域模型、Tool 定义以及
  Diagnosis、Envelope、Knowledge、Result API Schema 补充准确中文 Docstring。
- 替换目标文件中的占位描述，明确生产配置校验、租户权限、路由指标、Provider 状态统一、
  日志截断、知识作用域和响应边界；未给简单构造器增加重复说明。
- ADOS 静态扫描：11 个目标文件的缺失类 Docstring 和 Docstring warning 均归零。
- `venv/bin/python -m compileall -q ci_assistant ci_analysis_demo`：通过。
- `venv/bin/pytest -q`：`108 passed, 1 warning in 6.74s`；warning 与第一批相同。

### 第三批：持久化与剩余占位描述

- 为安全 HTML 解析、索引切片、知识处理结果、持久化实体与 Repository、SQLAlchemy
  Mixin、GitLab/Jenkins Client 和 Provider 补充中文类 Docstring。
- 替换主包非测试、非迁移代码中剩余的占位描述，覆盖异常响应、日志预处理、知识脱敏与
  切片、知识版本查询、事务中立 Repository、配置同步和默认 Tool 注册。
- ADOS 静态扫描：主包公共函数缺口、非测试类缺口及非测试/非迁移占位告警均归零。
- `venv/bin/python -m compileall -q ci_assistant ci_analysis_demo`：通过。
- `venv/bin/pytest -q`：`108 passed, 1 warning in 10.33s`；warning 与前两批相同。

### 第四批：剩余有效长度告警

- 校准应用生命周期、反馈 API、文档解析、Embedding 与缓存、ACL 检索、Reranker、反馈
  持久化、Webhook 审计、GitHub 日志和知识数据集导入等短 Docstring，补足安全边界、
  返回语义、降级行为和事务约束。
- 主包非测试、非迁移代码的 Docstring 长度告警归零；保留迁移入口和测试替身中的短描述，
  避免为满足长度阈值机械扩写。
- 对 50 个本次变更的 Python 文件移除 Docstring 后进行 AST 对比，全部与 `HEAD` 语义结构
  一致，确认未改变函数体、签名或运行逻辑。
- ADOS 最终静态扫描：公共函数缺口、主包非测试类缺口、主包非测试/非迁移告警和 Python
  解析错误均为零；`validate_adoption.py` 为 `Passed`，14 项检查全部通过。
- `venv/bin/python -m compileall -q ci_assistant ci_analysis_demo`：通过；
  `venv/bin/pytest -q`：`108 passed, 1 warning in 6.60s`；`git diff --check`：通过。
- 唯一 warning 仍为 FastAPI TestClient 对当前 Starlette 适配层的弃用提示。

### 第五批：旧 API 兼容契约

- 为 `ci_analysis_demo` 的 GitLab Client、环境配置、诊断与作业 Schema、RAG 结果、分析
  Trace、Tool 契约、错误规则和模型异常补充准确中文类 Docstring。
- 替换 RAG 命中属性和 Tool 结果属性中的占位描述，明确顺序、成功状态和缓存键语义；补充
  `ToolsExecutor` 的注册与异常隔离说明。
- 兼容包非测试类 Docstring 缺口归零；未修改旧接口字段、执行顺序、依赖或架构，也未处理
  私有实现和单纯长度告警。
- 最终扫描：全项目公共函数缺口、兼容包非测试类缺口和 Python 解析错误均为零；ADOS
  `validate_adoption.py` 为 `Passed`，14 项检查全部通过。
- `venv/bin/python -m compileall -q ci_assistant ci_analysis_demo` 和 `git diff --check` 通过；
  `venv/bin/pytest -q` 为 `108 passed, 1 warning in 6.37s`，warning 仍为既有的 Starlette
  TestClient 弃用提示。

### 第六批：诊断 API 语义说明

- 完善 `ci_assistant/api/diagnoses.py` 的内部派发函数及日志诊断、Run 诊断、结果查询接口
  Docstring，明确租户鉴权、预处理、持久化、Celery 派发和 Worker 后续取数边界。
- ADOS 静态扫描中该文件无 Docstring warning；移除 Docstring 后 AST 与 `HEAD` 一致。
- 专项回归 `8 passed, 1 warning`，源码编译和 `git diff --check` 通过；warning 为既有的
  Starlette TestClient 弃用提示。

### 第七批：诊断 Worker 生命周期

- 完善 `ci_assistant/workers/diagnosis_tasks.py` 的 Celery 任务入口与异步处理 Docstring，明确
  仅传诊断 ID、数据库取数、自动重试、安全失败日志、幂等返回、Provider 日志获取、租户
  ACL 检索、结果落库和连接池释放边界。
- 专项回归 `5 passed`；移除 Docstring 后 AST 与 `HEAD` 一致，源码编译和
  `git diff --check` 通过。
