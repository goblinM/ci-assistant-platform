# 评测说明

## 为什么要做评测

这个项目不是只看接口能不能返回，而是要验证 AI 分析结果是否稳定、可用、可解释。评测脚本用固定样例集调用接口，把模型输出转换成可统计指标，帮助定位问题出在模型、prompt、RAG 检索还是响应结构。

## 评测数据

评测样例位于：

```text
ci_analysis_demo/knowledge_docs/eval_cases.json
```

每条样例包含：

- `log_text`：CI 失败日志
- `expected_error_type`：期望错误类型
- `expected_keywords`：原因和建议中期望覆盖的关键词
- `expected_reference_titles`：RAG 希望命中的知识库文档标题

## 指标

### Schema valid rate

衡量接口返回是否符合 `AnalysisLogResponse`。

如果这个指标低，说明 LLM 输出不稳定，或者后端没有做好兜底和校验。

### Error type accuracy

衡量 `error_type` 是否等于人工标注。

这个指标主要评估模型分类能力和 prompt 约束是否有效。

### Top-k reference hit rate

衡量 RAG 返回的 `references` 是否命中期望知识文档。

这个指标主要评估检索质量。它和模型生成能力不同，更多受 embedding 模型、知识库内容、检索文本拼接方式、top-k、score 阈值影响。

### Avg keyword score

衡量 `summary/reason/suggestions` 是否覆盖期望关键词。

这个指标用于粗略判断建议是否包含关键排查点。

## 运行方式

普通 LLM 评测：

```bash
make eval
```

RAG 评测：

```bash
make eval-rag
```

评测前需要先启动服务：

```bash
make dev
```

## 面试讲法

我没有只做“接口能返回”的验证，而是构造了 20 条 CI 失败样例，分别标注期望错误类型、关键词和引用文档。评测时脚本会真实调用服务接口，然后统计 schema 有效率、错误类型准确率、RAG 引用命中率和关键词覆盖率。

这样做的价值是能拆解问题：如果 schema valid 低，说明结构化输出不稳定；如果 error type 低，说明模型分类或 prompt 有问题；如果 reference hit 低，说明 RAG 检索召回不好；如果 keyword score 低，说明建议不够贴近排查动作。
