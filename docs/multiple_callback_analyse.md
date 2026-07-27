# RAG 多路召回原理解析

> 本文中的“多路召回”指 multiple retrieval。文件名沿用 `multiple_callback_analyse.md`，但它与程序回调 callback 没有关系。

## 一、整体设计

多路召回的核心思想是：同一个检索 Query 分别从语义相似、关键词精确匹配和结构化属性匹配三个角度寻找知识文档，然后对结果合并、去重和重排。

```text
RAG Query
   ├── Semantic Retrieval：含义是否相近
   ├── Keyword Retrieval：关键术语是否精确出现
   └── Metadata Retrieval：错误类型等属性是否匹配
               ↓
           合并、去重
               ↓
          Hybrid Score
               ↓
           规则 Rerank
               ↓
            Final Top-K
```

三种召回方式解决的问题不同：

| 召回方式 | 主要作用 | 典型匹配内容 |
| --- | --- | --- |
| Semantic | 扩大召回范围，理解相近含义 | “模块不存在”与“Python 依赖缺失” |
| Keyword | 提高精确程度 | `ModuleNotFoundError`、`requests`、`403` |
| Metadata | 限制错误类型 | `error_type=dependency_missing` |

## 二、Semantic Retrieval

### 2.1 解决的问题

语义召回解决日志和知识文档表达不同，但含义相近的问题。

日志可能是：

```text
ModuleNotFoundError: No module named 'requests'
```

知识文档标题可能是：

```text
Python 依赖缺失导致构建失败
```

两段文本不完全相同，但语义上都属于 Python 依赖缺失。

### 2.2 底层逻辑

1. 将知识文档转换为 Embedding 向量。
2. 将清洗、改写后的 Query 转换为同维度向量。
3. 对 Query 和文档向量进行归一化。
4. 使用 FAISS 计算向量内积。
5. 归一化向量的内积等价于余弦相似度。
6. 过滤低于 `min_score` 的候选文档。

```text
query_vector = embedding(query)
doc_vector = embedding(document)

semantic_score = cosine_similarity(query_vector, doc_vector)
```

项目实现位于：

```text
ci_analysis_demo/services/rag_retriever.py
```

### 2.3 优点

- 不要求日志与知识文档使用完全相同的词。
- 可以处理同义词、自然语言描述和中英文混合表达。
- 对知识库中没有精确关键词标注的文档仍有召回能力。
- 面对新日志时具备一定泛化能力。

### 2.4 局限

- 可能召回“含义相近，但具体错误不同”的文档。
- 对包名、状态码和环境变量名等精确标识符不一定敏感。
- Embedding 模型和文档表达质量会直接影响召回结果。

## 三、Keyword Retrieval

### 3.1 解决的问题

技术日志中经常包含不能模糊理解的精确标识符，例如：

```text
ModuleNotFoundError
requests
requirements.txt
401
manifest unknown
No space left on device
```

这些词通常比笼统的语义相似更有诊断价值。

知识文档显式维护关键词：

```json
{
  "keywords": [
    "ModuleNotFoundError",
    "requests",
    "requirements.txt",
    "pip install"
  ]
}
```

### 3.2 底层逻辑

当前关键词召回会检查以下字段：

- `keywords`
- `tags`
- `error_types`
- `category`
- `title`

分数由精确术语命中和标题词重叠共同组成：

```text
keyword_score
    = 精确关键词命中数量 × 0.25
    + 标题词重叠数量 × 0.15
```

最终分数限制在 `0～1`：

```python
return min(
    1.0,
    exact_hits * 0.25 + title_overlap * 0.15,
)
```

### 3.3 优点

- 对异常类名、包名、状态码和配置名称非常敏感。
- 可解释性强，可以定位具体命中了哪些关键词。
- 不依赖 Embedding 模型。
- 能召回语义分数不高但精确术语高度匹配的文档。

### 3.4 局限

- 依赖知识文档维护高质量 `keywords`。
- 同义词、缩写没有进入关键词表时可能漏召回。
- 简单字符串包含可能产生误匹配。
- 当前是轻量关键词算法，文档规模扩大后可升级为 BM25。

## 四、Metadata Retrieval

### 4.1 解决的问题

当规则已经识别出错误类型后，可以优先召回相同类型的知识文档，减少跨错误类型误召回。

规则识别结果示例：

```python
primary_error = {
    "error_type": "dependency_missing",
    "keyword": "ModuleNotFoundError",
    "groups": ["requests"],
}
```

转换为 RAG Filter：

```python
rag_filters = {
    "error_type": "dependency_missing",
}
```

知识文档维护对应 Metadata：

```json
{
  "error_types": ["dependency_missing"]
}
```

### 4.2 底层逻辑

Metadata 匹配本质上是期望值与文档属性求交集：

```python
expected = {"dependency_missing"}
actual = {"dependency_missing", "dependency_conflict"}

matched = bool(expected & actual)
```

```text
primary_error.error_type
          ↓
document.error_types 是否包含该类型
          ↓
匹配：进入候选集
不匹配：过滤
```

### 4.3 优点

- 可以精确控制召回范围。
- 不依赖文本表达和 Embedding 模型质量。
- 匹配性能开销低。
- 可解释性强，可以直接说明文档与错误类型一致。
- 后续可以扩展到语言、项目、CI 阶段和技术栈等字段。

### 4.4 局限

- 依赖前置规则识别结果是否准确。
- Metadata 标注错误可能过滤掉正确文档。
- 严格过滤可能提高精确率，但降低召回率。
- 对规则无法识别的未知错误帮助有限。

## 五、三路召回如何合并

三条召回路径分别产生候选文档：

```python
semantic_scores = {
    doc_index: semantic_score,
}

keyword_indices = [
    # 关键词召回的文档索引
]

metadata_indices = [
    # Metadata 匹配的文档索引
]
```

然后按照文档索引合并并去重：

```python
merged_indices = list(dict.fromkeys([
    *semantic_scores.keys(),
    *keyword_indices,
    *metadata_indices,
]))
```

一个文档即使被三路同时召回，最终也只保留一次，同时记录召回来源：

```json
{
  "retrieval_sources": [
    "semantic",
    "keyword",
    "metadata"
  ]
}
```

通过 `retrieval_sources` 可以判断文档为什么被召回：

| 召回来源 | 含义 |
| --- | --- |
| 只有 `semantic` | 主要依靠语义泛化召回 |
| 只有 `keyword` | 主要依靠精确技术术语命中 |
| 只有 `metadata` | 主要依靠规则识别出的错误类型 |
| 三路同时命中 | 通常是可信度较高的候选文档 |

## 六、Hybrid Score

合并候选集后，使用三种分数计算综合分数：

```python
hybrid_score = (
    0.65 * semantic_score
    + 0.25 * keyword_score
    + 0.10 * metadata_score
)
```

当前权重设计：

| 通道 | 权重 | 作用 |
| --- | ---: | --- |
| Semantic | 0.65 | 提供主要语义泛化能力 |
| Keyword | 0.25 | 增强异常名、包名和状态码的精确匹配 |
| Metadata | 0.10 | 对规则识别结果提供稳定加分 |

假设一个文档的分数为：

```text
semantic_score = 0.80
keyword_score = 0.75
metadata_score = 1.00
```

则综合分数为：

```text
0.65 × 0.80 + 0.25 × 0.75 + 0.10 × 1.00
= 0.8075
```

这些权重不是永久固定值，后续应根据离线评测结果调整。

## 七、规则 Rerank

Hybrid Score 计算完成后，还会进行一次轻量规则重排：

- `error_type` 精确匹配时额外加 `0.10`。
- Query 与标题存在词重叠时，每个重叠词加 `0.03`。
- 标题词重叠加分上限为 `0.09`。

完整分数可以抽象为：

```text
final_score
  = semantic_score × 0.65
  + keyword_score × 0.25
  + metadata_score × 0.10
  + error_type_match_bonus
  + title_overlap_bonus
```

当前规则重排不需要额外模型，适合知识库规模较小、需要快速验证效果的阶段。后续如果评测证明规则重排能力不足，再考虑接入 Cross-Encoder、BGE Reranker 或 Cohere Rerank。

## 八、与 Query Rewrite 的配合

原始日志通常偏机器语言，而知识库更接近故障手册语言，因此检索前会补充结构化信息：

```text
ModuleNotFoundError: No module named 'requests'
error_type: dependency_missing
keyword: ModuleNotFoundError
package: requests
```

Query Rewrite 同时增强三条召回路径：

- Semantic 更容易理解这是依赖缺失问题。
- Keyword 可以精确命中异常名和包名。
- Metadata 使用相同的 `error_type` 过滤文档。

## 九、与 Tool Calling 的配合

`primary_error` 是 RAG 和 Tool Calling 的共享上下文：

```text
原始日志
   ↓
extract_primary_error_keyword
   ↓
primary_error
   ├── 构造 RAG Query 和 Metadata Filter
   └── 筛选 Tool Calling 候选工具
              ↓
       RAGResult + ToolResult
              ↓
             LLM
```

对应逻辑是：

```python
primary_error = extract_primary_error_keyword(log_text)

rag_result = retriever.retrieve(
    query=rag_query,
    top_k=3,
    filters={
        "error_type": primary_error["error_type"],
    },
)

tools_schema = tools_executor.get_tools_schema(
    text=log_text,
    trigger_keywords=[primary_error["keyword"]],
)
```

这样可以避免 RAG 和 Tool Calling 分别重复识别日志，并保证两个模块对主要错误的理解一致。

## 十、为什么比纯向量检索更可靠

以 `ModuleNotFoundError: requests` 为例：

1. Semantic 找到语义相近的“Python 依赖缺失排查”。
2. Keyword 精确命中 `ModuleNotFoundError`、`requests` 和 `requirements.txt`。
3. Metadata 确认文档属于 `dependency_missing`。
4. Rerank 将错误类型和标题都匹配的文档排到前面。

三路召回分别承担：

```text
Semantic：扩大召回范围
Keyword：提高精确程度
Metadata：限制错误类型
Rerank：决定最终顺序
```

纯向量检索容易出现“意思相近但细节不准确”，纯关键词检索容易出现“表达方式不同就无法命中”，纯 Metadata 又依赖规则分类。三者组合后，可以在召回率、精确率和可解释性之间取得更好的平衡。

## 十一、后续评测重点

三路召回上线后，不能只观察最终回答，需要分别评测检索阶段：

- `Recall@1`：第一篇文档是否命中预期文档。
- `Recall@3`：前三篇文档是否包含预期文档。
- `MRR`：预期文档在结果中的平均排名。
- `Metadata Hit Rate`：Metadata Filter 是否保留了正确文档。
- `Reference Precision`：返回引用中真正相关文档的比例。
- `retrieval_sources` 分布：正确文档主要由哪条路径召回。
- 各通道分数分布：判断 `0.65 / 0.25 / 0.10` 是否需要调整。

只有结合这些指标，才能判断问题出在 Query 清洗、Embedding、关键词标注、Metadata 规则、权重配置还是 Rerank。
