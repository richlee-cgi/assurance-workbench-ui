from app.cli import check_assurance_cli, check_azure, check_dataverse


def test_check_assurance_cli_reports_missing_path() -> None:
    result = check_assurance_cli("/definitely/missing/assurance")

    assert result.ok is False
    assert "Unable to run assurance" in result.message


def test_check_azure_reports_missing_path() -> None:
    result = check_azure("/definitely/missing/assurance")

    assert result.ok is False
    assert result.command == ["/definitely/missing/assurance", "azure", "check"]


def test_check_dataverse_reports_missing_path() -> None:
    result = check_dataverse("/definitely/missing/assurance")

    assert result.ok is False
    assert result.command == ["/definitely/missing/assurance", "dataverse", "check"]
