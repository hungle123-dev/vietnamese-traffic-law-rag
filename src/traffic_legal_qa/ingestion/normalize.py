"""Deterministic HTML-to-text normalization for legal source content."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Final

from traffic_legal_qa.ingestion.models import ReviewedTextReplacement

NORMALIZER_VERSION: Final = "1"
_BLOCK_TAGS: Final = frozenset(
    {"article", "br", "div", "h1", "h2", "h3", "li", "p", "section", "tr"}
)
_IGNORED_TAGS: Final = frozenset({"script", "style"})


class _LegalTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in _IGNORED_TAGS:
            self._ignored_depth += 1
        elif self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._line_break()

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORED_TAGS and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif self._ignored_depth == 0 and tag in _BLOCK_TAGS:
            self._line_break()

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self._parts.append(data)

    def _line_break(self) -> None:
        if self._parts and self._parts[-1] != "\n":
            self._parts.append("\n")

    def text(self) -> str:
        return "".join(self._parts)


def normalize_html(html: str) -> str:
    """Preserve legal text and numbering while making line boundaries reproducible."""

    parser = _LegalTextExtractor()
    parser.feed(html)
    parser.close()
    text = unicodedata.normalize("NFC", parser.text()).replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class ReviewedReplacementError(ValueError):
    """A curator-approved correction no longer matches the retrieved source."""


def apply_reviewed_replacements(
    text: str, replacements: tuple[ReviewedTextReplacement, ...]
) -> str:
    """Apply literal, exact-count corrections after deterministic HTML normalization."""

    for replacement in replacements:
        found_count = text.count(replacement.find)
        if found_count != replacement.expected_count:
            raise ReviewedReplacementError(
                f"reviewed correction matched {found_count} times, "
                f"expected {replacement.expected_count}: {replacement.reason}"
            )
        text = text.replace(replacement.find, replacement.replace)
    return text
