from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.api.dependencies import get_session
from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.persistence.connections import CIConnectionRepository
from ci_assistant.providers.base import AuthenticationError
from ci_assistant.services.webhooks import WebhookService


router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/{connection_id}/gitlab", status_code=202)
@router.post("/{connection_id}/jenkins", status_code=202)
async def receive_ci_webhook(
    connection_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    connection = await CIConnectionRepository(session).get_by_external_id(connection_id)
    if connection is None:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "CI connection not found",
            status_code=404,
        )
    try:
        provider = request.app.state.provider_manager.get(connection_id)
        outcome = await WebhookService().handle(
            session=session,
            provider=provider,
            connection=connection,
            headers=dict(request.headers),
            body=await request.body(),
        )
    except AuthenticationError as exc:
        raise PlatformError(
            ErrorCode.WEBHOOK_INVALID,
            str(exc),
            status_code=401,
        ) from exc

    if outcome.diagnosis_id is not None:
        dispatcher = getattr(request.app.state, "task_dispatcher", None)
        if dispatcher is not None:
            dispatcher("ci_assistant.diagnose", str(outcome.diagnosis_id))
    return {
        "request_id": request.state.request_id,
        "data": {
            "event_id": outcome.event_id,
            "diagnosis_id": outcome.diagnosis_id,
            "duplicate": outcome.duplicate,
        },
        "error": None,
    }
