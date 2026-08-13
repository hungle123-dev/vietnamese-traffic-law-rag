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


def test_fetch_catalog_ingests_all_reviewed_sources(
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
        ["fetch-catalog", "--catalog", str(fixture_catalog), "--data-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["succeeded"] == [{"document_id": "168/2024/NĐ-CP", "unit_count": 2}]
    assert payload["failed"] == []


def test_validate_snapshot_rejects_mismatched_parsed_metadata(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()
    monkeypatch.setattr(PortalClient, "fetch_raw", lambda _self, _source: raw_bytes)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["sources"][0]["reviewed_text_replacements"] = []
    fixture_catalog = tmp_path / "catalog.json"
    fixture_catalog.write_text(json.dumps(catalog), encoding="utf-8")

    fetch_result = CliRunner().invoke(
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
    assert fetch_result.exit_code == 0, fetch_result.output
    manifest = json.loads((tmp_path / "manifests/traffic-2026-08-13-v1.json").read_text())
    parsed_path = tmp_path / manifest["documents"][0]["parsed_path"]
    parsed = json.loads(parsed_path.read_text())
    parsed["metadata"]["content_sha256"] = "0" * 64
    parsed_path.write_text(json.dumps(parsed), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "validate-snapshot",
            "--snapshot-id",
            "traffic-2026-08-13-v1",
            "--data-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0


def test_report_snapshot_writes_validated_catalog_counts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()
    monkeypatch.setattr(PortalClient, "fetch_raw", lambda _self, _source: raw_bytes)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["sources"][0]["reviewed_text_replacements"] = []
    fixture_catalog = tmp_path / "catalog.json"
    fixture_catalog.write_text(json.dumps(catalog), encoding="utf-8")
    fetch_result = CliRunner().invoke(
        app,
        ["fetch-catalog", "--catalog", str(fixture_catalog), "--data-root", str(tmp_path)],
    )
    assert fetch_result.exit_code == 0, fetch_result.output

    result = CliRunner().invoke(
        app,
        [
            "report-snapshot",
            "--snapshot-id",
            "traffic-2026-08-13-v1",
            "--catalog",
            str(fixture_catalog),
            "--data-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    report = json.loads(Path(payload["report_path"]).read_text(encoding="utf-8"))
    assert isinstance(report["catalog_sha256"], str)
    assert report["catalog_document_count"] == 1
    assert report["totals"] == {
        "metadata_document_counts": {
            "fields": 1,
            "issuing_organs": 1,
            "majors": 1,
            "portal_document_type": 1,
            "signers": 1,
            "source_effect_status": 1,
        },
        "unit_count": 2,
        "unit_counts": {"article": 1, "point": 1},
        "unknown_status_document_count": 0,
    }


def test_rebuild_snapshot_uses_frozen_raw_bytes(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()
    monkeypatch.setattr(PortalClient, "fetch_raw", lambda _self, _source: raw_bytes)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["sources"][0]["reviewed_text_replacements"] = []
    fixture_catalog = tmp_path / "catalog.json"
    fixture_catalog.write_text(json.dumps(catalog), encoding="utf-8")
    runner = CliRunner()
    fetched = runner.invoke(
        app,
        ["fetch-catalog", "--catalog", str(fixture_catalog), "--data-root", str(tmp_path)],
    )
    assert fetched.exit_code == 0, fetched.output

    manifest_path = tmp_path / "manifests/traffic-2026-08-13-v1.json"
    manifest = json.loads(manifest_path.read_text())
    parsed_path = tmp_path / manifest["documents"][0]["parsed_path"]
    parsed = json.loads(parsed_path.read_text())
    parsed["artifact_version"] = "1"
    parsed_path.write_text(json.dumps(parsed), encoding="utf-8")

    rebuilt = runner.invoke(
        app,
        [
            "rebuild-snapshot",
            "--snapshot-id",
            "traffic-2026-08-13-v1",
            "--catalog",
            str(fixture_catalog),
            "--data-root",
            str(tmp_path),
        ],
    )

    assert rebuilt.exit_code == 0, rebuilt.output
    assert json.loads(rebuilt.output)["rebuilt"] == [
        {"document_id": "168/2024/NĐ-CP", "unit_count": 2}
    ]
