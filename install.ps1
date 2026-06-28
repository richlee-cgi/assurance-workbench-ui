param(
    [string] $InstallDir = "",
    [string] $RepoUrl = "https://github.com/richlee-cgi/assurance-workbench-ui.git",
    [string] $HostName = "127.0.0.1",
    [int] $Port = 8765
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $InstallDir) {
    if ((Test-Path (Join-Path $scriptDir ".git")) -and (Test-Path (Join-Path $scriptDir "pyproject.toml"))) {
        $InstallDir = $scriptDir
    }
    else {
        $InstallDir = "$HOME\dev\assurance-workbench-ui"
    }
}

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

function Get-EnvValue {
    param([string] $Name)
    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($processValue) {
        return $processValue
    }
    return [Environment]::GetEnvironmentVariable($Name, "User")
}

function ConvertFrom-SecureStringPlainText {
    param([SecureString] $SecureValue)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Configure-AtlassianEnv {
    if ((Get-EnvValue "ATLASSIAN_BASE_URL") -and (Get-EnvValue "ATLASSIAN_EMAIL") -and (Get-EnvValue "ATLASSIAN_API_TOKEN")) {
        Write-Info "Atlassian environment variables are already set."
        return
    }

    Write-Info ""
    $answer = Read-Host "Atlassian environment variables are not set. Configure them now and save them as user environment variables? [y/N]"
    if ($answer -notin @("y", "Y", "yes", "YES")) {
        Write-Info "Skipped Atlassian environment setup."
        return
    }

    $baseUrl = Read-Host "Atlassian base URL, for example https://example.atlassian.net"
    $email = Read-Host "Atlassian email"
    $token = ConvertFrom-SecureStringPlainText (Read-Host "Atlassian API token" -AsSecureString)

    if (-not $baseUrl -or -not $email -or -not $token) {
        Write-Info "Skipped Atlassian environment setup because one or more values were blank."
        return
    }

    [Environment]::SetEnvironmentVariable("ATLASSIAN_BASE_URL", $baseUrl, "User")
    [Environment]::SetEnvironmentVariable("ATLASSIAN_EMAIL", $email, "User")
    [Environment]::SetEnvironmentVariable("ATLASSIAN_API_TOKEN", $token, "User")
    $env:ATLASSIAN_BASE_URL = $baseUrl
    $env:ATLASSIAN_EMAIL = $email
    $env:ATLASSIAN_API_TOKEN = $token

    Write-Info "Saved Atlassian environment variables to the current user environment."
    Write-Info "Open a new PowerShell window if an existing terminal does not see them."
}

Require-Command git
$pythonCommand = Test-Python

Clone-Or-UpdateRepo
Set-Location $InstallDir

Write-Info "Creating virtual environment if needed"
Invoke-SelectedPython -PythonCommand $pythonCommand -Arguments @("-m", "venv", ".venv")

$isWindowsHost = Test-IsWindowsHost
$venvPython = if ($isWindowsHost) {
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
Configure-AtlassianEnv

Write-Info ""
Write-Info "Install complete."
Write-Info ""
Write-Info "Start or restart after reboot:"
Write-Info "  cd `"$InstallDir`""
Write-Info "  .\run.ps1"
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
if ($isWindowsHost) {
    Write-Info ""
    Write-Info "If PowerShell blocks activation, either run:"
    Write-Info "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
    Write-Info "or start with:"
    Write-Info "  .\run.ps1"
}
