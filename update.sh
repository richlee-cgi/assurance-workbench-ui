#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_DIR="${ASSURANCE_CLI_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/assurance-cli}"
PYTHON_BIN="${ASSURANCE_WORKBENCH_UI_PYTHON:-python3}"

info() {
  printf '%s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_clean_repo() {
  local repo_dir="$1"
  local name="$2"
  if [ ! -d "$repo_dir/.git" ]; then
    fail "$name repo was not found at $repo_dir"
  fi
  if [ -n "$(git -C "$repo_dir" status --porcelain)" ]; then
    fail "$name repo has local changes. Commit, stash or discard them before updating."
  fi
}

pull_repo() {
  local repo_dir="$1"
  local name="$2"
  info "Updating $name"
  git -C "$repo_dir" pull --ff-only
}

if ! command -v git >/dev/null 2>&1; then
  fail "git is required but was not found on PATH."
fi

if [ ! -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  info "Workbench virtualenv not found; creating .venv"
  "$PYTHON_BIN" -m venv "$SCRIPT_DIR/.venv"
fi

require_clean_repo "$SCRIPT_DIR" "Workbench"
require_clean_repo "$CLI_DIR" "assurance-cli"

pull_repo "$CLI_DIR" "assurance-cli"
pull_repo "$SCRIPT_DIR" "Workbench"

cd "$SCRIPT_DIR"

info "Updating Workbench virtualenv"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pip install --upgrade "$CLI_DIR"

info ""
info "Installed versions:"
.venv/bin/python -m pip show assurance-workbench-ui | sed -n 's/^Version: /  assurance-workbench-ui /p'
.venv/bin/assurance --version | sed 's/^/  /'
info ""
info "Update complete. Restart the server with:"
info "  ./run.sh"
