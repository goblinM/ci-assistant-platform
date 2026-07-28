from contextlib import asynccontextmanager
import os
from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import FastAPI

from ci_analysis_demo.clients.gitlab_client import GitLabClient
from ci_analysis_demo.core.config import get_settings
from ci_analysis_demo.core.logger import setup_logger
from ci_analysis_demo.routers.analysis_ci import router as analyze_router
from ci_analysis_demo.routers.job import router as job_router
from ci_analysis_demo.services.rag_retriever import LocalRetriever
from ci_analysis_demo.tools.register import create_default_tools_executor


KNOWLEDGE_DOCS_PATH = Path(__file__).resolve().parents[0] / "knowledge_docs" / "knowledge_docs.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用启动与关闭期间的资源生命周期。"""
    setup_logger()
    settings = get_settings()
    app.state.retriever = LocalRetriever(KNOWLEDGE_DOCS_PATH)
    gitlab_client = GitLabClient(
        base_url=settings.gitlab_base_url,
        private_token=settings.gitlab_private_token,
        timeout=settings.gitlab_timeout_seconds,
    )
    app.state.gitlab_client = gitlab_client
    app.state.tools_executor = create_default_tools_executor(gitlab_client=gitlab_client)
    yield


app = FastAPI(
    title="AI CI Assistant",
    description="CI failure log analysis API with LLM, RAG, and rule-based tool context.",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(job_router)
app.include_router(analyze_router)


def main():
    """运行当前模块的命令行入口。"""
    app_import = "main:app" if Path.cwd() == Path(__file__).resolve().parent else "ci_analysis_demo.main:app"
    uvicorn.run(
        app_import,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8080")),
        reload=True,
    )


if __name__ == "__main__":
    main()
