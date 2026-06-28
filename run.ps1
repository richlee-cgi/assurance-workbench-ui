param(
    [string] $HostName = "127.0.0.1",
    [int] $Port = 8765
)

$ErrorActionPreference = "Stop"

function Test-IsWindowsHost {
    return [System.IO.Path]::DirectorySeparatorChar -eq "\"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = if (Test-IsWindowsHost) {
    Join-Path $scriptDir ".venv\Scripts\python.exe"
}
else {
    Join-Path $scriptDir ".venv/bin/python"
}

if (-not (Test-Path $venvPython)) {
    Write-Error "Expected virtualenv Python at $venvPython. Run .\install.ps1 first, or create .venv and install the app manually."
    exit 1
}

Set-Location $scriptDir
if (-not $env:ATLASSIAN_BASE_URL -or -not $env:ATLASSIAN_EMAIL -or -not $env:ATLASSIAN_API_TOKEN) {
    Write-Warning "Atlassian environment variables are incomplete; Confluence/Jira evidence will fail until ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN are set."
}
Write-Host "Starting Assure-O-Matic 3000 Workbench at http://$HostName`:$Port"
& $venvPython -m uvicorn app.main:app --reload --host $HostName --port $Port
exit $LASTEXITCODE
