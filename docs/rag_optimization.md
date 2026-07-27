# RAG 实时优化记录

> 最后更新：2026-07-16  
> 状态说明：`DONE` 已完成，`DOING` 正在验证，`TODO` 尚未开始。

## 当前状态

| 优先级 | 优化项 | 状态 | 当前实现 |
| --- | --- | --- | --- |
| P0 | 知识库文档结构 | DONE | 文档显式维护 `error_types`、`keywords`，加载时校验必填字段和重复 ID，并兼容旧 case JSON |
| P0 | 日志 query 清洗 | DONE | 去 ANSI、时间戳、重复行，提取关键错误，限制 12 行和 2000 字符 |
| P0 | metadata 过滤 | DONE | `primary_error.error_type` 转成 RAG filter，扩大候选召回后过滤 |
| P0 | 统一检索结果 | DONE | 使用 `RAGResult` / `RAGDocument`，不再在主流程传裸 `list[dict]` |
| P0 | RAG trace | DONE | 记录 query、filters、top_k、candidate_count、doc IDs、titles、scores、sources、error types、duration 和 context length |
| P0 | context budget | DONE | `RAG_CONTEXT_MAX_CHARS` 控制知识上下文，超限时按文档顺序裁剪 |
| P1 | Hybrid Search | DONE | semantic 0.65 + keyword 0.25 + metadata 0.10 |
| P1 | 规则 Rerank | DONE | error type 精确匹配和标题词重叠加权 |
| P1 | Query Rewrite | DONE | 原始错误 query 补充 error type、关键词和包名 |
| P1 | 多路召回 | DONE | semantic、keyword、metadata 分别召回，合并去重后重排 |
| P1 | RAG + Tool 共享上下文 | DONE | 一次识别 `primary_error`，同时传给 RAG 和 Tool 候选过滤 |
| 验证 | 单元测试 | DONE | 覆盖 query、rewrite、metadata、规则重排、RAGResult、trace 和 context budget |
| 验证 | 离线 RAG 评测 | TODO | 增加 Recall@1/3、MRR、Metadata Hit Rate、Reference Precision |
| 演进 | 专用 Reranker | TODO | 评测证明规则重排不足后，再接 Cross-Encoder / BGE / Cohere |
| 演进 | 文档 chunk | TODO | 知识文档增长或单文档明显超长后再拆 chunk，并保留 parent_doc_id |
| 演进 | 持久化向量索引 | TODO | 当前启动时重建 FAISS；文档规模扩大后改为离线构建和版本化加载 |

## 当前链路

```text
raw log
  -> extract_primary_error_keyword (共享上下文)
  -> extract_query_from_log
  -> query rewrite
  -> semantic / keyword / metadata retrieval
  -> merge + deduplicate
  -> rule rerank
  -> RAGResult top-k
  -> context budget
  -> LLM + ToolResult
```

## 配置项

```dotenv
RETRIEVE_TOP_K=3
RAG_MIN_SCORE=0.25
RAG_CANDIDATE_MULTIPLIER=4
RAG_CONTEXT_MAX_CHARS=6000
```

`RAG_CANDIDATE_MULTIPLIER` 决定每一路初始候选规模。默认 top-k 为 3、倍数为 4，因此每一路最多先取 12 个候选，再合并重排得到最终 3 个。

## 更新日志

- `2026-07-16`：完成 P0 六项优化，统一 `RAGResult` 和 trace。
- `2026-07-16`：完成轻量 Hybrid Search、多路召回、规则重排和 query rewrite。
- `2026-07-16`：将 `primary_error` 作为 RAG 与 Tool Calling 的共享分析上下文。
- `2026-07-16`：新增 6 个 RAG 单元测试并通过全量测试。

## 原始设计记录

### RAG 优化
#### 第二优先级
1. Hybrid Search：关键词打分数
    纯向量检索可能把语义相近但不精确的文档召回，Hybrid可以增强精确匹配。
2. Rerank 重排
    1. 不接复杂的reranker,可以先做规则重排
    2. 后续升级cross-encoder reranker，LLM reranker，bge-reranker，cohere rerank
3. query rewrite：让检索 query 更像知识库语言
4. 多路召回：你的 RAG 可以这样升级
    ```
    1. semantic retrieval 语义检索
    2. keyword retrieval 关键词检索
    3. metadata retrieval 元数据检索

    query_text
      ↓
    semantic top 10
    keyword top 10
    metadata same error_type top 10
      ↓
    merge 去重
      ↓
    rerank
      ↓
    final top 3
    ```
5. RAG 和 Tool Calling 配合
    ```
    规则/日志识别 primary_error
      ↓
    RAG 用 primary_error 做 metadata filter
      ↓
    Tool Calling 用 primary_error 选择候选工具
      ↓
    LLM 综合 RAG + ToolResult
   就是说，primary_error 是两个模块的共享上下文。
   primary_error = extract_primary_error_keyword(log_text)
   类似 
    rag_filters = {
        "error_type": primary_error["error_type"] if primary_error else None
    }
    
    rag_result = retriever.retrieve(
        query=rag_query,
        top_k=3,
        filters=rag_filters,
    )
    
    tools_schema = tools_executor.get_candidate_tools_schema(
        log_text=log_text,
        tags=["ci"],
    )
    ```
6. RAG优化后的service流程
```
primary_error = extract_primary_error_keyword(log_text)

query_text = extract_query_from_log(log_text)

rag_query = build_rag_query(
    log_query=query_text,
    primary_error=primary_error,
)

rag_filters = {}
if primary_error:
    rag_filters["error_type"] = primary_error["error_type"]

rag_result = retriever.retrieve(
    query=rag_query,
    top_k=settings.retrieve_top_k,
    filters=rag_filters,
)

tool_context = collect_tool_context(...)

prompt = build_final_prompt(
    log_text=log_text,
    rag_context=rag_result.to_prompt_context(),
    tool_context=tool_context.to_prompt_context(),
)
```
7. RAG测评
```
评测指标：

Recall@1
Recall@3
MRR
Metadata Hit Rate
Reference Precision
Context Length
Recall@3
def recall_at_k(hit_doc_ids: list[str], expected_doc_ids: list[str]) -> bool:
    return any(doc_id in hit_doc_ids for doc_id in expected_doc_ids)
MRR
def mrr(hit_doc_ids: list[str], expected_doc_ids: list[str]) -> float:
    for index, doc_id in enumerate(hit_doc_ids, start=1):
        if doc_id in expected_doc_ids:
            return 1 / index
    return 0.0
```
