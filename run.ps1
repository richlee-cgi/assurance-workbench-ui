param(
    [string] $HostName = "127.0.0.1",
    [int] $Port = 8765
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = if ($IsWindows) {
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
Write-Host "Starting Assure-O-Matic 3000 Workbench at http://$HostName`:$Port"
& $venvPython -m uvicorn app.main:app --reload --host $HostName --port $Port
exit $LASTEXITCODE
