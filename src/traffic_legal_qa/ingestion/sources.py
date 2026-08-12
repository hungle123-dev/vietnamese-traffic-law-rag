import re
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader

DEFAULT_TIMEOUT_SECONDS = 30
MAX_PDF_BYTES = 32 * 1024 * 1024
_GAZETTE_HEADER_RE = re.compile(r"^(?:\d+\s+)?CÔNG BÁO/Số .+?(?:\s+\d+)?$", re.IGNORECASE)


@dataclass(frozen=True)
class DownloadedPdf:
    raw_content: bytes
    text: str
    page_count: int


def fetch_pdf(source_url: str) -> DownloadedPdf:
    """Download an official text PDF and retain its exact bytes for provenance."""
    parsed_url = urlparse(source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("PDF source URL must use http or https")

    request = Request(source_url, headers={"User-Agent": "traffic-legal-qa/0.1"})
    # ponytail: one request for manual ingestion; add bounded retries in a batch runner.
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310
        content_type = response.headers.get_content_type()
        if content_type not in {"application/pdf", "application/octet-stream"}:
            raise ValueError(f"Expected a PDF response, got {content_type!r}")
        declared_length = response.headers.get("Content-Length")
        if declared_length is not None and int(declared_length) > MAX_PDF_BYTES:
            raise ValueError(f"PDF exceeds {MAX_PDF_BYTES} byte limit")
        raw_content = response.read(MAX_PDF_BYTES + 1)

    if len(raw_content) > MAX_PDF_BYTES:
        raise ValueError(f"PDF exceeds {MAX_PDF_BYTES} byte limit")
    if not raw_content.startswith(b"%PDF-"):
        raise ValueError("Response is not a PDF file")

    reader = PdfReader(BytesIO(raw_content))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")
    text = normalize_pdf_text("\n".join(page.extract_text() or "" for page in reader.pages))
    if not text:
        raise ValueError("PDF contains no extractable text")
    return DownloadedPdf(raw_content=raw_content, text=text, page_count=len(reader.pages))


def normalize_pdf_text(content: str) -> str:
    """Keep legal hierarchy lines while removing recurring Công báo page headers."""
    lines = (" ".join(line.split()) for line in content.splitlines())
    return "\n".join(line for line in lines if line and not _GAZETTE_HEADER_RE.match(line))
