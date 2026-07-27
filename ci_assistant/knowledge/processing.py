from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal


MAX_DOCUMENT_CHARS = 5_000_000
_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*(?:bearer|basic)\s+)[^\s]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{10,}\b"),
]


@dataclass(frozen=True)
class ProcessedDocument:
    normalized_content: str
    content_hash: str
    chunks: list[str]


def mask_secrets(content: str) -> str:
    masked = content
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            masked = pattern.sub(r"\1***", masked)
        else:
            masked = pattern.sub("***", masked)
    return masked


def normalize_document(content: str, format: Literal["markdown", "json"]) -> str:
    if not content.strip():
        raise ValueError("document content cannot be empty")
    if len(content) > MAX_DOCUMENT_CHARS:
        raise ValueError("document exceeds maximum size")
    if format == "json":
        try:
            value = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON document: {exc.msg}") from exc
        content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return mask_secrets(content).strip()


def chunk_document(content: str, *, target_chars: int = 800) -> list[str]:
    if target_chars < 300:
        raise ValueError("target_chars must be at least 300")
    blocks = re.split(r"\n(?=#{1,6}\s)|\n{2,}", content)
    chunks: list[str] = []
    current = ""
    for block in (item.strip() for item in blocks if item.strip()):
        if len(block) > target_chars:
            pieces = [
                block[start : start + target_chars]
                for start in range(0, len(block), target_chars)
            ]
        else:
            pieces = [block]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if current and len(candidate) > target_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def process_document(content: str, format: Literal["markdown", "json"]) -> ProcessedDocument:
    normalized = normalize_document(content, format)
    return ProcessedDocument(
        normalized_content=normalized,
        content_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        chunks=chunk_document(normalized),
    )

