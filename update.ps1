param(
    [string] $CliDir = "",
    [string] $PythonCommand = "python"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultCliDir = Join-Path (Split-Path -Parent $scriptDir) "assurance-cli"

function Write-Info {
    param([string] $Message)
    Write-Host $Message
}

function Fail {
    param([string] $Message)
    Write-Error $Message
    exit 1
}

function Assert-LastCommandSucceeded {
    param([string] $Description)
    if ($LASTEXITCODE -ne 0) {
        Fail "$Description failed with exit code $LASTEXITCODE."
    }
}

function Test-IsWindowsHost {
    return [System.IO.Path]::DirectorySeparatorChar -eq "\"
}

function Require-CleanRepo {
    param(
        [string] $RepoDir,
        [string] $Name
    )
    if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
        Fail "$Name repo was not found at $RepoDir"
    }
    $status = git -C $RepoDir status --porcelain
    if ($status) {
        Fail "$Name repo has local changes. Commit, stash or discard them before updating."
    }
}

function Pull-Repo {
    param(
        [string] $RepoDir,
        [string] $Name
    )
    Write-Info "Updating $Name"
    git -C $RepoDir pull --ff-only
    Assert-LastCommandSucceeded "git pull $Name"
}

function Install-CliDependency {
    if ($CliDir) {
        Require-CleanRepo -RepoDir $CliDir -Name "assurance-cli"
        Pull-Repo -RepoDir $CliDir -Name "assurance-cli"
        & $venvPython -m pip install --upgrade $CliDir
        Assert-LastCommandSucceeded "assurance-cli local install"
        return
    }

    if (Test-Path (Join-Path $defaultCliDir ".git")) {
        Require-CleanRepo -RepoDir $defaultCliDir -Name "assurance-cli"
        Pull-Repo -RepoDir $defaultCliDir -Name "assurance-cli"
        & $venvPython -m pip install --upgrade $defaultCliDir
        Assert-LastCommandSucceeded "assurance-cli sibling install"
        return
    }

    Write-Info "No sibling assurance-cli checkout found; updating CLI dependency from GitHub main"
    & $venvPython -m pip install --upgrade --force-reinstall --no-deps "assurance-cli @ git+https://github.com/richlee-cgi/assurance-cli.git@main"
    Assert-LastCommandSucceeded "assurance-cli GitHub install"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "git is required but was not found on PATH."
}

$isWindowsHost = Test-IsWindowsHost
$venvPython = if ($isWindowsHost) {
    Join-Path $scriptDir ".venv\Scripts\python.exe"
}
else {
    Join-Path $scriptDir ".venv/bin/python"
}

if (-not (Test-Path $venvPython)) {
    Write-Info "Workbench virtualenv not found; creating .venv"
    & $PythonCommand -m venv (Join-Path $scriptDir ".venv")
    Assert-LastCommandSucceeded "virtualenv creation"
}

Require-CleanRepo -RepoDir $scriptDir -Name "Workbench"

Pull-Repo -RepoDir $scriptDir -Name "Workbench"

Set-Location $scriptDir

Write-Info "Updating Workbench virtualenv"
& $venvPython -m pip install --upgrade pip
Assert-LastCommandSucceeded "pip upgrade"
& $venvPython -m pip install -e ".[dev]"
Assert-LastCommandSucceeded "Workbench install"
Install-CliDependency

Write-Info ""
Write-Info "Installed versions:"
& $venvPython -m pip show assurance-workbench-ui | Select-String "^Version: " | ForEach-Object { "  assurance-workbench-ui " + $_.ToString().Replace("Version: ", "") }
$assuranceExe = if ($isWindowsHost) {
    Join-Path $scriptDir ".venv\Scripts\assurance.exe"
}
else {
    Join-Path $scriptDir ".venv/bin/assurance"
}
& $assuranceExe --version | ForEach-Object { "  $_" }
Write-Info ""
Write-Info "Update complete. Restart the server with:"
Write-Info "  .\run.ps1"
