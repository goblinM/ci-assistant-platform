"""
RAG: 检索增强生成
知识库服务
"""
import json
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer

KNOWLEDGE_DOCS_PATH = Path(__file__).resolve().parents[1] / "knowledge_docs" / "knowledge_docs.json"
STOP_WORDS = {"a", "an", "and", "as", "in", "is", "no", "of", "on", "or", "the", "to"}


def _tokenize(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text)
        if token.strip() and token.lower() not in STOP_WORDS
    }


def retrieve_top_k(log_text: str, k: int = 3) -> list[dict]:
    """
    rag 检索返回 top-k 知识片段。

    当前先用关键词重叠做最小可用检索，后续可以替换为向量检索。
    """
    with KNOWLEDGE_DOCS_PATH.open("r", encoding="utf-8") as f:
        docs = json.load(f)

    query_tokens = _tokenize(log_text)

    def score(doc: dict) -> int:
        searchable = " ".join(
            [
                doc.get("title", ""),
                doc.get("content", ""),
                doc.get("category", ""),
                " ".join(doc.get("tags", [])),
            ]
        )
        doc_tokens = _tokenize(searchable)
        return len(query_tokens & doc_tokens)

    scored_docs = [(score(doc), doc) for doc in docs]
    ranked_docs = [
        doc
        for doc_score, doc in sorted(scored_docs, key=lambda item: item[0], reverse=True)
        if doc_score > 0
    ]
    return ranked_docs[:k]


def sentence_transformer():
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")