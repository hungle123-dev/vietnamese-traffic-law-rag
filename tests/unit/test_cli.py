from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from traffic_legal_qa.cli import app
from traffic_legal_qa.ingestion.portal import PortalClient

FIXTURES = Path(__file__).parents[1] / "fixtures"
CATALOG = Path("data/catalog/smoke-168-2024-nd-cp.json")


def test_fetch_portal_only_ingests_a_catalogued_document(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()
    monkeypatch.setattr(PortalClient, "fetch_raw", lambda _self, _source: raw_bytes)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["sources"][0]["reviewed_text_replacements"] = []
    fixture_catalog = tmp_path / "catalog.json"
    fixture_catalog.write_text(json.dumps(catalog), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "fetch-portal",
            "--catalog",
            str(fixture_catalog),
            "--document-id",
            "168/2024/NĐ-CP",
            "--data-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["unit_count"] == 2
