from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.dependencies import get_session
from ci_assistant.api.auth import enforce_tenant
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.persistence.knowledge import KnowledgeRepository
from ci_assistant.schemas.knowledge import (
    CreateKnowledgeDocument,
    KnowledgeDocumentView,
)
from ci_assistant.services.knowledge import KnowledgeService


router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _dispatch(request: Request, task: str, identifier: str) -> None:
    dispatcher = getattr(request.app.state, "task_dispatcher", None)
    if dispatcher is not None:
        dispatcher(task, identifier)


@router.post("/documents", status_code=202)
async def create_document(
    payload: CreateKnowledgeDocument,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
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
    enforce_tenant(request, tenant_id)
    documents = await KnowledgeRepository(session).list_scoped(
        tenant_id, project_id=project_id
    )
    return {
        "request_id": request.state.request_id,
        "data": [KnowledgeDocumentView.model_validate(item) for item in documents],
        "error": None,
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    tenant_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
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
    enforce_tenant(request, tenant_id)
    _dispatch(request, "ci_assistant.reindex_knowledge", str(tenant_id))
    return {
        "request_id": request.state.request_id,
        "data": {"tenant_id": tenant_id, "status": "queued"},
        "error": None,
    }
