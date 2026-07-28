import asyncio
import io
import json
import sys
import zipfile
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from ci_assistant.core.config import UnlimitedOCRConfig
from ci_assistant.knowledge.document_parsers import (
    DocumentParser,
    DocumentParserUnavailableError,
    DocumentParsingError,
    PyMuPDFRenderer,
    UnlimitedOCRClient,
    parse_docx,
    parse_html,
)


def _docx_bytes(paragraphs: list[tuple[str | None, str]]) -> bytes:
    body = []
    for style, text in paragraphs:
        properties = (
            f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        )
        body.append(f"<w:p>{properties}<w:r><w:t>{text}</w:t></w:r></w:p>")
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        + "".join(body)
        + "</w:body></w:document>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def test_html_parser_preserves_headings_and_ignores_active_content() -> None:
    """验证 HTML 解析保留结构且忽略脚本和样式内容。"""
    content = parse_html(
        b"<html><style>secret-style</style><h1>Failure</h1>"
        b"<p>Missing dependency.</p><script>steal()</script></html>"
    )

    assert "# Failure" in content
    assert "Missing dependency." in content
    assert "secret-style" not in content
    assert "steal()" not in content


def test_docx_parser_extracts_heading_and_paragraph() -> None:
    """验证 DOCX 原生解析保留标题和正文。"""
    content = parse_docx(
        _docx_bytes(
            [
                ("Heading1", "Build failure"),
                (None, "Install the missing package."),
            ]
        )
    )

    assert content == "# Build failure\n\nInstall the missing package."


def test_docx_parser_rejects_excessive_compression_ratio() -> None:
    """验证 DOCX ZIP Bomb 压缩比限制。"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "A" * 100_000)

    with pytest.raises(DocumentParsingError, match="compression ratio"):
        parse_docx(output.getvalue(), max_compression_ratio=5)


def test_docx_parser_rejects_xml_entities() -> None:
    """验证 DOCX 拒绝 DTD 和 XML 实体扩展。"""
    document = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE document [<!ENTITY x "expanded">]>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/'
        b'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&x;</w:t>'
        b"</w:r></w:p></w:body></w:document>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", document)

    with pytest.raises(DocumentParsingError, match="entities"):
        parse_docx(output.getvalue())


def test_pdf_parser_renders_pages_and_calls_unlimited_ocr() -> None:
    """验证 PDF 页面只通过 Unlimited-OCR 进入解析结果。"""
    renderer = MagicMock()
    renderer.render.return_value = [b"page-one", b"page-two"]
    ocr_client = AsyncMock()
    ocr_client.parse_images.return_value = "# Parsed\n\nResult"
    parser = DocumentParser(
        UnlimitedOCRConfig(enabled=True),
        pdf_renderer=renderer,
        ocr_client=ocr_client,
    )

    result = asyncio.run(parser.parse("failure.pdf", b"%PDF-fixture"))

    assert result.source_format == "pdf"
    assert result.content == "# Parsed\n\nResult"
    renderer.render.assert_called_once_with(b"%PDF-fixture")
    ocr_client.parse_images.assert_awaited_once_with([b"page-one", b"page-two"])


def test_pdf_parser_requires_configured_unlimited_ocr() -> None:
    """验证未配置 Unlimited-OCR 时 PDF 返回稳定不可用错误。"""
    parser = DocumentParser(UnlimitedOCRConfig(enabled=False))

    with pytest.raises(DocumentParserUnavailableError, match="not configured"):
        asyncio.run(parser.parse("failure.pdf", b"%PDF-fixture"))


def test_pymupdf_renderer_enforces_page_and_pixel_limits(monkeypatch) -> None:
    """验证 PDF 渲染器执行页数与总像素限制。"""
    page = MagicMock()
    pixmap = MagicMock(width=100, height=100)
    pixmap.tobytes.return_value = b"png"
    page.get_pixmap.return_value = pixmap
    document = MagicMock(needs_pass=False, page_count=2)
    document.__iter__.return_value = iter([page, page])
    fitz = MagicMock()
    fitz.open.return_value = document
    fitz.Matrix.return_value = MagicMock()
    monkeypatch.setitem(sys.modules, "fitz", fitz)

    with pytest.raises(DocumentParsingError, match="page limit"):
        PyMuPDFRenderer(
            dpi=150,
            max_pages=1,
            max_total_pixels=1_000_000,
        ).render(b"%PDF")

    document.page_count = 2
    with pytest.raises(DocumentParsingError, match="pixel limit"):
        PyMuPDFRenderer(
            dpi=150,
            max_pages=2,
            max_total_pixels=15_000,
        ).render(b"%PDF")

    document.close.assert_called()


def test_document_parser_rejects_unsupported_and_oversized_files() -> None:
    """验证文件类型和上传大小限制。"""
    parser = DocumentParser(
        UnlimitedOCRConfig(enabled=False, max_file_bytes=1_000_000)
    )

    with pytest.raises(DocumentParsingError, match="supported file formats"):
        asyncio.run(parser.parse("failure.txt", b"text"))
    with pytest.raises(DocumentParsingError, match="maximum size"):
        asyncio.run(parser.parse("failure.html", b"x" * 1_000_001))

    text_limited = DocumentParser(
        UnlimitedOCRConfig(
            enabled=False,
            max_file_bytes=1_000_000,
            max_parsed_chars=100_000,
        )
    )
    with pytest.raises(DocumentParsingError, match="maximum text size"):
        asyncio.run(
            text_limited.parse(
                "failure.html",
                ("<p>" + "x" * 100_001 + "</p>").encode(),
            )
        )


def test_unlimited_ocr_client_uses_openai_compatible_multimage_request() -> None:
    """验证 Unlimited-OCR HTTP 请求包含多页图片和固定推理约束。"""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        """捕获 OCR 请求并返回兼容响应。"""
        captured["request"] = request
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "# Parsed"}}]},
        )

    client = UnlimitedOCRClient(
        UnlimitedOCRConfig(
            enabled=True,
            base_url="http://ocr.internal:10000",
            model="Unlimited-OCR",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.parse_images([b"page-one", b"page-two"]))

    request = captured["request"]
    payload = json.loads(request.content)
    image_content = payload["messages"][0]["content"][1:]
    assert result == "# Parsed"
    assert str(request.url) == "http://ocr.internal:10000/v1/chat/completions"
    assert payload["model"] == "Unlimited-OCR"
    assert payload["images_config"] == {"image_mode": "base"}
    assert len(image_content) == 2
    assert all(
        item["image_url"]["url"].startswith("data:image/png;base64,")
        for item in image_content
    )
