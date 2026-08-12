from typer.testing import CliRunner

from traffic_legal_qa.cli import app


def test_fetch_pdf_help_is_available() -> None:
    result = CliRunner().invoke(app, ["fetch-pdf", "--help"])

    assert result.exit_code == 0
    assert "--issued-date" in result.output
    assert "--content-url" in result.output
