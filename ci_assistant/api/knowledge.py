from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.dependencies import get_session
from ci_assistant.api.auth import enforce_tenant
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.knowledge.document_parsers import (
    DocumentParser,
    DocumentParserUnavailableError,
    DocumentParsingError,
)
from ci_assistant.persistence.knowledge import KnowledgeRepository
from ci_assistant.schemas.knowledge import (
    CreateKnowledgeDocument,
    CreateParsedKnowledgeDocument,
    KnowledgeDocumentView,
)
from ci_assistant.services.knowledge import KnowledgeService


router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _dispatch(request: Request, task: str, identifier: str) -> None:
    dispatcher = getattr(request.app.state, "task_dispatcher", None)
    if dispatcher is not None:
        dispatcher(task, identifier)


async def _read_upload(file: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > max_bytes:
            raise PlatformError(
                ErrorCode.KNOWLEDGE_INVALID,
                "Uploaded document exceeds maximum size",
                status_code=413,
            )
    return bytes(data)


@router.post("/documents", status_code=202)
async def create_document(
    payload: CreateKnowledgeDocument,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """创建 ``create_document`` 对应的领域对象或结果。"""
    enforce_tenant(request, payload.tenant_id)
    created = await KnowledgeService().create(session, payload)
    if not created.duplicate:
        _dispatch(request, "ci_assistant.ingest_document", str(created.document.id))
    return {
        "request_id": request.state.request_id,
        "data": {
            "document": KnowledgeDocumentView.model_validate(created.document),
            "ingestion_job_id": created.job.id if created.job else None,
            "duplicate": created.duplicate,
        },
        "error": None,
    }


@router.get("/documents")
async def list_documents(
    tenant_id: UUID,
    request: Request,
    project_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
):
    """列出 ``list_documents`` 对应的数据。"""
    enforce_tenant(request, tenant_id)
    documents = await KnowledgeRepository(session).list_scoped(
        tenant_id, project_id=project_id
    )
    return {
        "request_id": request.state.request_id,
        "data": [KnowledgeDocumentView.model_validate(item) for item in documents],
        "error": None,
    }


@router.post("/documents/files", status_code=202)
async def create_document_file(
    request: Request,
    tenant_id: UUID = Form(),
    title: str = Form(min_length=1, max_length=500),
    provider: Literal["gitlab", "jenkins", "github"] | None = Form(default=None),
    project_id: UUID | None = Form(default=None),
    source_type: str = Form(default="customer", max_length=50),
    source_url: str | None = Form(default=None, max_length=1000),
    license: str | None = Form(default=None, max_length=100),
    file: UploadFile = File(),
    session: AsyncSession = Depends(get_session),
):
    """解析 PDF、DOCX 或 HTML 文件并进入现有知识入库链路。"""
    enforce_tenant(request, tenant_id)
    parser: DocumentParser | None = getattr(
        request.app.state,
        "document_parser",
        None,
    )
    if parser is None:
        raise PlatformError(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Document parser is not configured",
            status_code=503,
        )
    data = await _read_upload(file, parser.max_file_bytes)
    try:
        parsed = await parser.parse(file.filename or "", data)
    except DocumentParserUnavailableError as exc:
        raise PlatformError(
            ErrorCode.SERVICE_UNAVAILABLE,
            str(exc),
            status_code=503,
        ) from exc
    except DocumentParsingError as exc:
        raise PlatformError(
            ErrorCode.KNOWLEDGE_INVALID,
            str(exc),
            status_code=422,
        ) from exc
    payload = CreateParsedKnowledgeDocument(
        tenant_id=tenant_id,
        project_id=project_id,
        provider=provider,
        title=title,
        format=parsed.source_format,
        content=parsed.content,
        source_type=source_type,
        source_url=source_url,
        license=license,
    )
    created = await KnowledgeService().create(session, payload)
    if not created.duplicate:
        _dispatch(request, "ci_assistant.ingest_document", str(created.document.id))
    return {
        "request_id": request.state.request_id,
        "data": {
            "document": KnowledgeDocumentView.model_validate(created.document),
            "ingestion_job_id": created.job.id if created.job else None,
            "duplicate": created.duplicate,
        },
        "error": None,
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    tenant_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """获取 ``get_document`` 对应的数据。"""
    enforce_tenant(request, tenant_id)
    document = await KnowledgeRepository(session).get(document_id)
    if document is None or document.tenant_id != tenant_id or document.status == "deleted":
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Knowledge document not found",
            status_code=404,
        )
    return {
        "request_id": request.state.request_id,
        "data": KnowledgeDocumentView.model_validate(document),
        "error": None,
    }


@router.delete("/documents/{document_id}", status_code=202)
async def delete_document(
    document_id: UUID,
    tenant_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """删除 ``delete_document`` 对应的数据。"""
    enforce_tenant(request, tenant_id)
    document = await KnowledgeService().delete(session, document_id, tenant_id)
    if document is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Knowledge document not found",
            status_code=404,
        )
    _dispatch(request, "ci_assistant.ingest_document", str(document.id))
    return {
        "request_id": request.state.request_id,
        "data": {"document_id": document.id, "status": "deleted"},
        "error": None,
    }


@router.post("/reindex", status_code=202)
async def reindex(tenant_id: UUID, request: Request):
    """执行 ``reindex`` 对应的知识库处理流程。"""
    enforce_tenant(request, tenant_id)
    _dispatch(request, "ci_assistant.reindex_knowledge", str(tenant_id))
    return {
        "request_id": request.state.request_id,
        "data": {"tenant_id": tenant_id, "status": "queued"},
        "error": None,
    }
