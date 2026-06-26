#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${ASSURANCE_WORKBENCH_UI_REPO:-https://github.com/richlee-cgi/assurance-workbench-ui.git}"
HOST="${ASSURANCE_WORKBENCH_UI_HOST:-127.0.0.1}"
PORT="${ASSURANCE_WORKBENCH_UI_PORT:-8765}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd || true)"

default_install_dir() {
  if [ -n "${ASSURANCE_WORKBENCH_UI_DIR:-}" ]; then
    printf '%s' "$ASSURANCE_WORKBENCH_UI_DIR"
    return
  fi
  if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/.git" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    printf '%s' "$SCRIPT_DIR"
    return
  fi
  printf '%s' "$HOME/dev/assurance-workbench-ui"
}

INSTALL_DIR="$(default_install_dir)"

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

shell_profile_path() {
  case "$(basename "${SHELL:-}")" in
    zsh) printf '%s' "$HOME/.zshrc" ;;
    bash) printf '%s' "$HOME/.bashrc" ;;
    *) printf '%s' "$HOME/.profile" ;;
  esac
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

write_atlassian_profile_block() {
  local profile_path="$1"
  local base_url="$2"
  local email="$3"
  local api_token="$4"
  local temp_file
  temp_file="$(mktemp)"
  mkdir -p "$(dirname "$profile_path")"
  touch "$profile_path"
  awk '
    $0 == "# >>> assurance-workbench-ui >>>" { skip=1; next }
    $0 == "# <<< assurance-workbench-ui <<<" { skip=0; next }
    skip != 1 { print }
  ' "$profile_path" >"$temp_file"
  {
    printf '\n# >>> assurance-workbench-ui >>>\n'
    printf 'export ATLASSIAN_BASE_URL=%s\n' "$(shell_quote "$base_url")"
    printf 'export ATLASSIAN_EMAIL=%s\n' "$(shell_quote "$email")"
    printf 'export ATLASSIAN_API_TOKEN=%s\n' "$(shell_quote "$api_token")"
    printf '# <<< assurance-workbench-ui <<<\n'
  } >>"$temp_file"
  mv "$temp_file" "$profile_path"
}

configure_atlassian_env() {
  if [ -n "${ATLASSIAN_BASE_URL:-}" ] && [ -n "${ATLASSIAN_EMAIL:-}" ] && [ -n "${ATLASSIAN_API_TOKEN:-}" ]; then
    info "Atlassian environment variables are already set in this shell."
    return
  fi
  if [ ! -r /dev/tty ]; then
    info "Atlassian environment variables are not set. Configure them before running Confluence/Jira evidence."
    return
  fi

  local answer
  printf '\nAtlassian environment variables are not set. Configure them now and save them to your shell profile? [y/N] ' >/dev/tty
  read -r answer </dev/tty
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      info "Skipped Atlassian environment setup."
      return
      ;;
  esac

  local base_url email api_token profile_path
  printf 'Atlassian base URL, for example https://example.atlassian.net: ' >/dev/tty
  read -r base_url </dev/tty
  printf 'Atlassian email: ' >/dev/tty
  read -r email </dev/tty
  printf 'Atlassian API token: ' >/dev/tty
  stty -echo </dev/tty
  read -r api_token </dev/tty
  stty echo </dev/tty
  printf '\n' >/dev/tty

  if [ -z "$base_url" ] || [ -z "$email" ] || [ -z "$api_token" ]; then
    info "Skipped Atlassian environment setup because one or more values were blank."
    return
  fi

  profile_path="$(shell_profile_path)"
  write_atlassian_profile_block "$profile_path" "$base_url" "$email" "$api_token"
  info "Saved Atlassian environment variables to $profile_path"
  info "Open a new terminal, or run: source \"$profile_path\""
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
configure_atlassian_env

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
