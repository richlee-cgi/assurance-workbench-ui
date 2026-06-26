param(
    [string] $InstallDir = "$HOME\dev\assurance-workbench-ui",
    [string] $RepoUrl = "https://github.com/richlee-cgi/assurance-workbench-ui.git",
    [string] $HostName = "127.0.0.1",
    [int] $Port = 8765
)

$ErrorActionPreference = "Stop"

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

function Require-Command {
    param([string] $Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Fail "$Name is required but was not found on PATH."
    }
}

function Test-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return "py"
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
        if ($LASTEXITCODE -eq 0) {
            return "python"
        }
    }

    Fail "Python 3.11+ is required. Install Python from python.org or winget, then rerun this script."
}

function Invoke-SelectedPython {
    param(
        [string] $PythonCommand,
        [string[]] $Arguments
    )

    if ($PythonCommand -eq "py") {
        & py -3 @Arguments
        Assert-LastCommandSucceeded "Python command"
    }
    else {
        & python @Arguments
        Assert-LastCommandSucceeded "Python command"
    }
}

function Clone-Or-UpdateRepo {
    if (-not (Test-Path $InstallDir)) {
        $parent = Split-Path -Parent $InstallDir
        if ($parent) {
            New-Item -ItemType Directory -Force -Path $parent | Out-Null
        }
        Write-Info "Cloning Workbench into $InstallDir"
        git clone $RepoUrl $InstallDir
        Assert-LastCommandSucceeded "git clone"
        return
    }

    if (-not (Test-Path (Join-Path $InstallDir ".git"))) {
        Fail "$InstallDir exists but is not a Git repository."
    }

    Write-Info "Workbench repo already exists at $InstallDir"
    Push-Location $InstallDir
    try {
        $status = git status --porcelain
        if ($status) {
            Write-Info "Local changes detected; skipping automatic git pull."
            return
        }
        Write-Info "Updating existing checkout with git pull --ff-only"
        git pull --ff-only
        Assert-LastCommandSucceeded "git pull"
    }
    finally {
        Pop-Location
    }
}

function Report-OptionalTool {
    param([string] $Name)
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        Write-Info "Found optional tool: $Name"
    }
    else {
        Write-Info "Optional tool not found: $Name"
    }
}

Require-Command git
$pythonCommand = Test-Python

Clone-Or-UpdateRepo
Set-Location $InstallDir

Write-Info "Creating virtual environment if needed"
Invoke-SelectedPython -PythonCommand $pythonCommand -Arguments @("-m", "venv", ".venv")

$venvPython = if ($IsWindows) {
    Join-Path $InstallDir ".venv\Scripts\python.exe"
}
else {
    Join-Path $InstallDir ".venv/bin/python"
}
if (-not (Test-Path $venvPython)) {
    Fail "Expected virtualenv Python was not created at $venvPython"
}

Write-Info "Installing/updating Workbench and CLI dependency"
& $venvPython -m pip install --upgrade pip
Assert-LastCommandSucceeded "pip upgrade"
& $venvPython -m pip install -e ".[dev]"
Assert-LastCommandSucceeded "pip install"

Write-Info "Checking optional provider CLIs"
Report-OptionalTool az
Report-OptionalTool gh
Report-OptionalTool pac

Write-Info ""
Write-Info "Install complete."
Write-Info ""
Write-Info "Run:"
Write-Info "  cd `"$InstallDir`""
if ($IsWindows) {
    Write-Info "  .\.venv\Scripts\Activate.ps1"
}
else {
    Write-Info "  . .venv/bin/activate"
}
Write-Info "  python -m uvicorn app.main:app --reload --host $HostName --port $Port"
Write-Info ""
Write-Info "Open:"
Write-Info "  http://$HostName`:$Port"
Write-Info ""
Write-Info "Authenticate optional providers when needed:"
Write-Info "  az login"
Write-Info "  gh auth login"
Write-Info "  pac auth create --deviceCode"
Write-Info ""
Write-Info "Before Confluence/Jira evidence, set Atlassian environment variables in the terminal that starts Workbench:"
Write-Info "  `$env:ATLASSIAN_BASE_URL = `"https://example.atlassian.net`""
Write-Info "  `$env:ATLASSIAN_EMAIL = `"you@example.com`""
Write-Info "  `$env:ATLASSIAN_API_TOKEN = `"...`""
if ($IsWindows) {
    Write-Info ""
    Write-Info "If PowerShell blocks activation, either run:"
    Write-Info "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
    Write-Info "or start without activation:"
    Write-Info "  .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host $HostName --port $Port"
}
