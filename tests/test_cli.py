from app.cli import check_assurance_cli


def test_check_assurance_cli_reports_missing_path() -> None:
    result = check_assurance_cli("/definitely/missing/assurance")

    assert result.ok is False
    assert "Unable to run assurance" in result.message
