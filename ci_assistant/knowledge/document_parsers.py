from __future__ import annotations

import base64
import io
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree

import httpx

from ci_assistant.core.config import UnlimitedOCRConfig


class DocumentParsingError(ValueError):
    """表示文档格式无效、内容为空或超出安全解析限制。"""


class DocumentParserUnavailableError(DocumentParsingError):
    """表示文档解析依赖或外部 OCR 服务暂时不可用。"""


@dataclass(frozen=True)
class ParsedDocument:
    """封装已安全解析的文本正文及其原始文件格式。"""

    content: str
    source_format: str


class PDFRenderer(Protocol):
    """定义把受限 PDF 字节渲染为逐页图片的协议。"""

    def render(self, data: bytes) -> list[bytes]:
        """在资源限制内把 PDF 字节渲染为逐页 PNG。"""
        ...


class PyMuPDFRenderer:
    """使用 PyMuPDF 在受限资源范围内渲染 PDF。"""

    def __init__(
        self,
        *,
        dpi: int,
        max_pages: int,
        max_total_pixels: int,
    ) -> None:
        self.dpi = dpi
        self.max_pages = max_pages
        self.max_total_pixels = max_total_pixels

    def render(self, data: bytes) -> list[bytes]:
        """校验页数、加密和总像素限制后，将 PDF 页面渲染为 PNG。"""
        try:
            import fitz
        except ImportError as exc:
            raise DocumentParserUnavailableError("PyMuPDF is not installed") from exc
        try:
            document = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise DocumentParsingError("invalid PDF document") from exc
        try:
            if document.needs_pass:
                raise DocumentParsingError("password-protected PDF is not supported")
            if document.page_count < 1:
                raise DocumentParsingError("PDF document has no pages")
            if document.page_count > self.max_pages:
                raise DocumentParsingError("PDF page limit exceeded")
            matrix = fitz.Matrix(self.dpi / 72, self.dpi / 72)
            images: list[bytes] = []
            total_pixels = 0
            for page in document:
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                total_pixels += pixmap.width * pixmap.height
                if total_pixels > self.max_total_pixels:
                    raise DocumentParsingError("PDF pixel limit exceeded")
                images.append(pixmap.tobytes("png"))
            return images
        finally:
            document.close()


class UnlimitedOCRClient:
    """调用独立 Unlimited-OCR OpenAI-compatible 推理服务。"""

    def __init__(
        self,
        config: UnlimitedOCRConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model
        self.timeout_seconds = config.timeout_seconds
        self.transport = transport

    async def parse_images(self, images: list[bytes]) -> str:
        """将多页 PNG 发送给 Unlimited-OCR 并返回 Markdown 文本。"""
        if not images:
            raise DocumentParsingError("OCR input has no pages")
        content = [{"type": "text", "text": "Multi page parsing."}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                    + base64.b64encode(image).decode("ascii")
                },
            }
            for image in images
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
            "max_tokens": 32768,
            "images_config": {"image_mode": "base"},
            "custom_params": {"ngram_size": 35, "window_size": 1024},
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                trust_env=False,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise DocumentParserUnavailableError("Unlimited-OCR request failed") from exc
        if response.status_code >= 400:
            raise DocumentParserUnavailableError(
                f"Unlimited-OCR returned HTTP {response.status_code}"
            )
        try:
            result = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise DocumentParsingError("Unlimited-OCR returned an invalid response") from exc
        if not isinstance(result, str) or not result.strip():
            raise DocumentParsingError("Unlimited-OCR returned empty content")
        return result.strip()


class _SafeHTMLTextParser(HTMLParser):
    """只提取本地 HTML 可见文本，不执行脚本、样式或外部资源请求。"""

    _BLOCK_TAGS = {"p", "div", "section", "article", "li", "tr", "pre", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """记录安全结构分隔，并进入脚本、样式等主动内容的屏蔽区。"""
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in self._BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        """结束当前 HTML 结构块或主动内容屏蔽区。"""
        if tag in {"script", "style", "noscript"}:
            self.hidden_depth = max(self.hidden_depth - 1, 0)
            return
        if not self.hidden_depth and (
            tag in self._BLOCK_TAGS or re.fullmatch(r"h[1-6]", tag)
        ):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """只收集脚本、样式和 noscript 屏蔽区之外的可见文本。"""
        if not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        """返回规范化的 Markdown 风格文本。"""
        content = "".join(self.parts)
        content = re.sub(r"[ \t]+", " ", content)
        content = re.sub(r" *\n *", "\n", content)
        return re.sub(r"\n{3,}", "\n\n", content).strip()


def parse_html(data: bytes) -> str:
    """安全提取 HTML 标题、正文和表格文本，不访问外部资源。"""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentParsingError("HTML document must use UTF-8") from exc
    parser = _SafeHTMLTextParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as exc:
        raise DocumentParsingError("invalid HTML document") from exc
    result = parser.text()
    if not result:
        raise DocumentParsingError("HTML document has no readable content")
    return result


def parse_docx(
    data: bytes,
    *,
    max_members: int = 1_000,
    max_uncompressed_bytes: int = 50_000_000,
    max_compression_ratio: int = 100,
) -> str:
    """在 ZIP Bomb 限制下提取 DOCX 段落和标题。"""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentParsingError("invalid DOCX document") from exc
    with archive:
        members = archive.infolist()
        if len(members) > max_members:
            raise DocumentParsingError("DOCX member limit exceeded")
        total_size = sum(member.file_size for member in members)
        if total_size > max_uncompressed_bytes:
            raise DocumentParsingError("DOCX uncompressed size limit exceeded")
        for member in members:
            compressed = max(member.compress_size, 1)
            if member.file_size > compressed * max_compression_ratio:
                raise DocumentParsingError("DOCX compression ratio limit exceeded")
        try:
            xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise DocumentParsingError("DOCX document.xml is missing") from exc
    upper_xml = xml.upper()
    if b"<!DOCTYPE" in upper_xml or b"<!ENTITY" in upper_xml:
        raise DocumentParsingError("DOCX XML entities are not supported")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise DocumentParsingError("invalid DOCX XML") from exc
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(namespace + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(namespace + "t")).strip()
        if not text:
            continue
        style = paragraph.find(
            f"{namespace}pPr/{namespace}pStyle"
        )
        style_name = style.get(namespace + "val", "") if style is not None else ""
        heading = re.fullmatch(r"Heading([1-6])", style_name, re.IGNORECASE)
        paragraphs.append(f"{'#' * int(heading.group(1))} {text}" if heading else text)
    result = "\n\n".join(paragraphs)
    if not result:
        raise DocumentParsingError("DOCX document has no readable content")
    return result


class DocumentParser:
    """按文件格式选择安全原生解析或 Unlimited-OCR。"""

    def __init__(
        self,
        config: UnlimitedOCRConfig,
        *,
        pdf_renderer: PDFRenderer | None = None,
        ocr_client: UnlimitedOCRClient | None = None,
    ) -> None:
        self.config = config
        self.max_file_bytes = config.max_file_bytes
        self.max_parsed_chars = config.max_parsed_chars
        self.pdf_renderer = pdf_renderer or PyMuPDFRenderer(
            dpi=config.pdf_dpi,
            max_pages=config.max_pdf_pages,
            max_total_pixels=config.max_total_pixels,
        )
        self.ocr_client = ocr_client or (
            UnlimitedOCRClient(config) if config.enabled else None
        )

    async def parse(self, filename: str, data: bytes) -> ParsedDocument:
        """解析上传文件并返回可进入现有知识处理链路的 Markdown。"""
        if not data:
            raise DocumentParsingError("uploaded document is empty")
        if len(data) > self.max_file_bytes:
            raise DocumentParsingError("uploaded document exceeds maximum size")
        suffix = Path(filename).suffix.lower()
        if suffix in {".html", ".htm"}:
            return self._result(parse_html(data), "html")
        if suffix == ".docx":
            return self._result(parse_docx(data), "docx")
        if suffix == ".pdf":
            if self.ocr_client is None:
                raise DocumentParserUnavailableError("Unlimited-OCR is not configured")
            images = self.pdf_renderer.render(data)
            content = await self.ocr_client.parse_images(images)
            return self._result(content, "pdf")
        raise DocumentParsingError("supported file formats are PDF, DOCX and HTML")

    def _result(self, content: str, source_format: str) -> ParsedDocument:
        if len(content) > self.max_parsed_chars:
            raise DocumentParsingError("parsed document exceeds maximum text size")
        return ParsedDocument(content, source_format)
