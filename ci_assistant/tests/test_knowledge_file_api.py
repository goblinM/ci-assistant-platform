from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from ci_assistant.api.dependencies import get_session
from ci_assistant.knowledge.document_parsers import ParsedDocument
from ci_assistant.main import create_app
from ci_assistant.persistence.entities import IngestionJob, KnowledgeDocument
from ci_assistant.services.knowledge import CreatedKnowledge, KnowledgeService


def test_html_file_upload_enters_existing_knowledge_pipeline(monkeypatch) -> None:
    """验证 HTML 文件解析后复用现有知识持久化与派发链路。"""
    app = create_app()
    parser = MagicMock(max_file_bytes=1_000_000)
    parser.parse = AsyncMock(
        return_value=ParsedDocument("# Failure\n\nMissing dependency.", "html")
    )
    app.state.document_parser = parser
    dispatched: list[tuple[str, str]] = []
    app.state.task_dispatcher = lambda task, identifier: dispatched.append(
        (task, identifier)
    )
    tenant_id = UUID("00000000-0000-0000-0000-000000000001")
    document = KnowledgeDocument(
        id=uuid4(),
        tenant_id=tenant_id,
        project_id=None,
        provider="github",
        title="Failure guide",
        format="html",
        source_type="customer",
        source_url=None,
        license=None,
        content_hash="a" * 64,
        version=1,
        status="uploaded",
        content="# Failure\n\nMissing dependency.",
    )
    job = IngestionJob(
        id=uuid4(),
        document_id=document.id,
        status="queued",
        idempotency_key=f"ingest:{document.id}:1",
        error=None,
    )
    captured = {}

    async def fake_create(self, session, payload):
        """捕获文件上传转换后的知识负载。"""
        captured["payload"] = payload
        return CreatedKnowledge(document, job, False)

    async def fake_session():
        """提供无需数据库连接的测试 Session。"""
        yield MagicMock()

    monkeypatch.setattr(KnowledgeService, "create", fake_create)
    app.dependency_overrides[get_session] = fake_session

    response = TestClient(app).post(
        "/api/v1/knowledge/documents/files",
        data={
            "tenant_id": str(tenant_id),
            "title": "Failure guide",
            "provider": "github",
        },
        files={"file": ("guide.html", b"<h1>Failure</h1>", "text/html")},
    )

    assert response.status_code == 202
    assert captured["payload"].format == "html"
    assert captured["payload"].provider == "github"
    parser.parse.assert_awaited_once_with("guide.html", b"<h1>Failure</h1>")
    assert dispatched == [("ci_assistant.ingest_document", str(document.id))]


def test_pdf_upload_reports_unavailable_ocr_service() -> None:
    """验证 PDF 上传在 OCR 未配置时返回稳定 503 Envelope。"""
    app = create_app()
    tenant_id = "00000000-0000-0000-0000-000000000001"

    async def fake_session():
        """提供无需数据库连接的测试 Session。"""
        yield MagicMock()

    app.dependency_overrides[get_session] = fake_session
    response = TestClient(app).post(
        "/api/v1/knowledge/documents/files",
        data={"tenant_id": tenant_id, "title": "Scanned PDF"},
        files={"file": ("scan.pdf", b"%PDF-fixture", "application/pdf")},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
