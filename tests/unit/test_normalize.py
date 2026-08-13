import pytest

from traffic_legal_qa.ingestion.models import ReviewedTextReplacement
from traffic_legal_qa.ingestion.normalize import (
    ReviewedReplacementError,
    apply_reviewed_replacements,
    normalize_html,
)


def test_normalize_html_preserves_legal_line_boundaries_and_discards_script() -> None:
    html = "<div>Điều 1. Phạm vi</div><p>1. Nội dung&nbsp;chính</p><script>ignored()</script>"

    assert normalize_html(html) == "Điều 1. Phạm vi\n1. Nội dung chính"


def test_reviewed_replacement_requires_an_exact_match_count() -> None:
    replacement = ReviewedTextReplacement(
        find="đ) Portal typo",
        replace="d) Corrected label",
        expected_count=1,
        evidence_url="https://example.test/signed.pdf",
        reason="Validated against the signed source.",
    )

    assert apply_reviewed_replacements("đ) Portal typo", (replacement,)) == "d) Corrected label"
    with pytest.raises(ReviewedReplacementError, match="matched 0 times"):
        apply_reviewed_replacements("d) Already corrected", (replacement,))
