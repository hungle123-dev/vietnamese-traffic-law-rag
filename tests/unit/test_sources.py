import pytest

from traffic_legal_qa.ingestion.sources import fetch_pdf, normalize_pdf_text


def test_normalize_pdf_text_removes_gazette_headers_without_losing_hierarchy() -> None:
    content = """76 CÔNG BÁO/Số 977 + 978/Ngày 24-8-2024
Chương I
NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Nội dung quy định.
CÔNG BÁO/Số 977 + 978/Ngày 24-8-2024 77
"""

    assert normalize_pdf_text(content) == (
        "Chương I\nNHỮNG QUY ĐỊNH CHUNG\nĐiều 1. Phạm vi điều chỉnh\nNội dung quy định."
    )


def test_fetch_pdf_rejects_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http or https"):
        fetch_pdf("file:///tmp/traffic-law.pdf")
