#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ASSURANCE_WORKBENCH_UI_REPO:-https://github.com/richlee-cgi/assurance-workbench-ui.git}"
INSTALL_DIR="${ASSURANCE_WORKBENCH_UI_DIR:-$HOME/dev/assurance-workbench-ui}"
HOST="${ASSURANCE_WORKBENCH_UI_HOST:-127.0.0.1}"
PORT="${ASSURANCE_WORKBENCH_UI_PORT:-8765}"

info() {
  printf '%s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but was not found on PATH."
}

python_command() {
  if command -v python3 >/dev/null 2>&1; then
    printf 'python3'
    return
  fi
  if command -v python >/dev/null 2>&1; then
    printf 'python'
    return
  fi
  fail "Python 3.11+ is required but was not found on PATH."
}

check_python_version() {
  local python_bin="$1"
  "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
    || fail "Python 3.11+ is required. Found: $("$python_bin" --version 2>&1)"
}

clone_or_update_repo() {
  if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$(dirname "$INSTALL_DIR")"
    info "Cloning Workbench into $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    return
  fi

  if [ ! -d "$INSTALL_DIR/.git" ]; then
    fail "$INSTALL_DIR exists but is not a Git repository."
  fi

  info "Workbench repo already exists at $INSTALL_DIR"
  cd "$INSTALL_DIR"
  if [ -n "$(git status --porcelain)" ]; then
    info "Local changes detected; skipping automatic git pull."
    return
  fi
  info "Updating existing checkout with git pull --ff-only"
  git pull --ff-only
}

report_optional_tool() {
  if command -v "$1" >/dev/null 2>&1; then
    info "Found optional tool: $1"
  else
    info "Optional tool not found: $1"
  fi
}

require_command git
PYTHON_BIN="$(python_command)"
check_python_version "$PYTHON_BIN"

clone_or_update_repo
cd "$INSTALL_DIR"

info "Creating virtual environment if needed"
"$PYTHON_BIN" -m venv .venv

info "Installing/updating Workbench and CLI dependency"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

info "Checking optional provider CLIs"
report_optional_tool az
report_optional_tool gh
report_optional_tool pac

info ""
info "Install complete."
info ""
info "Start or restart after reboot:"
info "  cd \"$INSTALL_DIR\""
info "  ./run.sh"
info ""
info "Open:"
info "  http://$HOST:$PORT"
info ""
info "Authenticate optional providers when needed:"
info "  az login"
info "  gh auth login"
info "  pac auth create --deviceCode"
info ""
info "Before Confluence/Jira evidence, set Atlassian environment variables in the terminal that starts Workbench:"
info "  export ATLASSIAN_BASE_URL=\"https://example.atlassian.net\""
info "  export ATLASSIAN_EMAIL=\"you@example.com\""
info "  export ATLASSIAN_API_TOKEN=\"...\""
