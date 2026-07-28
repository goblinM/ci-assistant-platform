from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ci_assistant.core.config import PlatformSettings
from ci_assistant.persistence.entities import CIConnection, Tenant


async def sync_configuration(
    session: AsyncSession,
    settings: PlatformSettings,
) -> None:
    """执行 ``sync_configuration`` 对应的领域操作。"""
    tenant = await session.get(Tenant, settings.app.tenant_id)
    if tenant is None:
        tenant = Tenant(
            id=settings.app.tenant_id,
            name=settings.app.tenant_name,
            slug=settings.app.tenant_slug,
        )
        session.add(tenant)
        await session.flush()
    else:
        tenant.name = settings.app.tenant_name
        tenant.slug = settings.app.tenant_slug

    for configured in settings.ci.connections:
        connection = (
            await session.execute(
                select(CIConnection).where(
                    CIConnection.tenant_id == tenant.id,
                    CIConnection.external_id == configured.id,
                )
            )
        ).scalar_one_or_none()
        public_config = {
            "token_env": configured.token_env,
            "username_env": configured.username_env,
            "webhook_secret_env": configured.webhook_secret_env,
        }
        if connection is None:
            session.add(
                CIConnection(
                    tenant_id=tenant.id,
                    external_id=configured.id,
                    provider=configured.type,
                    base_url=configured.base_url,
                    config=public_config,
                )
            )
        else:
            connection.provider = configured.type
            connection.base_url = configured.base_url
            connection.config = public_config
    await session.flush()

