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
由 `docs/ci_assistant_platform_development.md`、`docs/ci_assistant_platform_tracker.md`、
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
