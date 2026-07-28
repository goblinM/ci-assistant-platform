from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

from ci_assistant.api.exception_handlers import (
    platform_error_handler,
    unhandled_error_handler,
)
from ci_assistant.api.diagnoses import router as diagnoses_router
from ci_assistant.api.connections import router as connections_router
from ci_assistant.api.knowledge import router as knowledge_router
from ci_assistant.api.observability import MetricsMiddleware, router as metrics_router
from ci_assistant.api.health import ReadinessCheck, router as health_router
from ci_assistant.api.middleware import RequestIDMiddleware
from ci_assistant.api.auth import TenantAuthMiddleware
from ci_assistant.api.webhooks import router as webhooks_router
from ci_assistant.core.config import load_settings
from ci_assistant.core.errors import PlatformError
from ci_assistant.persistence.database import Database
from ci_assistant.providers.manager import build_provider_manager
from ci_assistant.services.bootstrap import sync_configuration


def create_app(
    *,
    readiness_checks: Mapping[str, ReadinessCheck] | None = None,
    initialize_infrastructure: bool = False,
) -> FastAPI:
    """创建 ``create_app`` 对应的领域对象或结果。"""
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """管理应用启动与关闭期间的资源生命周期。"""
        if not initialize_infrastructure:
            yield
            return

        from redis.asyncio import Redis

        settings = load_settings()
        database = Database.from_config(settings.database)
        redis = Redis.from_url(settings.redis.url.get_secret_value())

        async def database_ready() -> None:
            """检查 ``database_ready`` 对应的就绪状态。"""
            async with database.session() as session:
                await session.execute(text("SELECT 1"))

        async def redis_ready() -> None:
            """检查 ``redis_ready`` 对应的就绪状态。"""
            await redis.ping()

        application.state.settings = settings
        application.state.database = database
        application.state.redis = redis
        application.state.provider_manager = build_provider_manager(settings)
        from ci_assistant.workers.celery_app import app as celery_app

        application.state.task_dispatcher = (
            (lambda task, identifier: celery_app.send_task(task, args=[identifier]))
            if celery_app is not None
            else None
        )
        async with database.session() as session:
            await sync_configuration(session, settings)
        application.state.readiness_checks = {
            "database": database_ready,
            "redis": redis_ready,
        }
        try:
            yield
        finally:
            await redis.aclose()
            await database.dispose()

    app = FastAPI(
        title="CI Assistant Platform",
        version="0.6.0",
        description="Private-deployable CI failure diagnosis platform.",
        lifespan=lifespan,
    )
    app.state.readiness_checks = dict(readiness_checks or {})
    app.add_middleware(TenantAuthMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    app.include_router(diagnoses_router)
    app.include_router(connections_router)
    app.include_router(knowledge_router)
    app.include_router(metrics_router)
    app.include_router(webhooks_router)
    return app


app = create_app(initialize_infrastructure=True)


def main() -> None:
    """运行当前模块的命令行入口。"""
    uvicorn.run(
        "ci_assistant.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8080")),
        reload=os.getenv("APP_RELOAD", "false").lower() == "true",
    )
