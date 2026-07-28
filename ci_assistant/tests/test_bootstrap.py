import asyncio
from unittest.mock import AsyncMock, MagicMock

from ci_assistant.core.config import load_settings
from ci_assistant.services.bootstrap import sync_configuration


def test_bootstrap_creates_default_tenant_without_secrets() -> None:
    """验证 ``test_bootstrap_creates_default_tenant_without_secrets`` 所描述的预期行为。"""
    session = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.flush = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    settings = load_settings(environ={})

    asyncio.run(sync_configuration(session, settings))

    tenant = session.add.call_args_list[0].args[0]
    assert tenant.id == settings.app.tenant_id
    assert tenant.slug == "default"

