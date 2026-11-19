#!/usr/bin/env bash
# MAES CLI Installer
# Usage: git clone https://github.com/Maxxidata/maxxi-ai-engineering-system.git
#        cd maxxi-ai-engineering-system && bash install.sh
#
# Flags:
#   --editable    Install in editable mode (pip install -e) instead of pipx.
#                 Useful for contributors who modify the CLI source.
set -euo pipefail

# ─── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR/template/scripts/tools"

EDITABLE=false
for arg in "$@"; do
  [[ "$arg" == "--editable" ]] && EDITABLE=true
done

if [[ ! -d "$TOOLS_DIR" ]]; then
  echo "Error: $TOOLS_DIR not found." >&2
  echo "Run this script from the root of the cloned maxxi-ai-engineering-system repo." >&2
  exit 1
fi

# ─── Helpers ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()     { echo -e "${GREEN}✓${NC} $1"; }
warn()   { echo -e "${YELLOW}⚠${NC}  $1"; }
info()   { echo -e "${BLUE}→${NC} $1"; }
err()    { echo -e "${RED}✗${NC} $1" >&2; }
die()    { err "$1"; exit 1; }
header() { echo -e "\n${BOLD}$1${NC}"; }

# ─── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   MAES — Maxxi AI Engineering System     ║${NC}"
echo -e "${BOLD}║   CLI Installer (local)                  ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ─── Python 3.9+ ───────────────────────────────────────────────────────────────
header "Checking prerequisites"

if ! command -v python3 &>/dev/null; then
  die "Python 3.9+ is required. Install it from https://python.org and re-run."
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9 ]]; then
  die "Python $PYTHON_VERSION detected. MAES requires Python 3.9+."
fi

ok "Python $PYTHON_VERSION"

# ─── pipx ──────────────────────────────────────────────────────────────────────
header "Installing pipx"

if command -v pipx &>/dev/null; then
  ok "pipx already installed ($(pipx --version))"
else
  info "pipx not found — installing..."

  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew &>/dev/null; then
    brew install pipx
    pipx ensurepath
  else
    python3 -m pip install --user --quiet pipx
    python3 -m pipx ensurepath
  fi

  ok "pipx installed"
fi

# Ensure pipx bin dir is in PATH for the rest of this script
# (ensurepath modifies shell profiles but doesn't affect the current session)
PIPX_BIN_DIR="$(python3 -m pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
export PATH="$PIPX_BIN_DIR:$PATH"

# ─── Install MAES ──────────────────────────────────────────────────────────────
header "Installing maes"

info "Source: $TOOLS_DIR"

if [[ "$EDITABLE" == "true" ]]; then
  info "Mode: editable (pip install -e)"
  python3 -m pip install --quiet -e "$TOOLS_DIR[all]"
  ok "maes installed in editable mode (anthropic + openai + mcp SDKs ready)"
else
  if pipx list 2>/dev/null | grep -q "package maes "; then
    # Clean uninstall + install avoids the 'uv venv already exists, use --clear'
    # failure that pipx install --force hits on newer uv backends.
    info "maes already installed — uninstalling previous version..."
    pipx uninstall maes --quiet >/dev/null 2>&1 || true
  fi
  pipx install "$TOOLS_DIR" --quiet
  # Inject all optional SDKs into the isolated pipx environment:
  #   anthropic: Claude  |  openai: GitHub Models + Gemini (OpenAI-compatible)
  #   mcp: required by 'maes serve' (Model Context Protocol stdio server)
  info "Injecting LLM provider + MCP SDKs..."
  pipx inject maes anthropic openai mcp --quiet \
    || warn "pipx inject failed — run: pipx inject maes anthropic openai mcp"
  ok "maes installed (anthropic + openai + mcp SDKs ready)"
fi

# ─── PATH check ────────────────────────────────────────────────────────────────
header "PATH"

if ! command -v maes &>/dev/null; then
  warn "maes not in PATH yet — this is expected on a fresh install."
  warn "Run one of the following and then re-open your terminal:"
  echo ""
  echo -e "  ${YELLOW}# bash${NC}"
  echo -e "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
  echo ""
  echo -e "  ${YELLOW}# zsh${NC}"
  echo -e "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && source ~/.zshrc"
  echo ""
  PATH_OK=false
else
  ok "maes is in PATH ($(command -v maes))"
  PATH_OK=true
fi

# ─── Validate ──────────────────────────────────────────────────────────────────
if [[ "$PATH_OK" == "true" ]]; then
  header "Validating installation"
  if maes doctor 2>/dev/null | grep -q "Python"; then
    ok "maes doctor passed"
  else
    warn "maes doctor reported issues — run 'maes doctor' after setup to review"
  fi
fi

# ─── Provider check ────────────────────────────────────────────────────────────
header "LLM provider"

PROVIDER_FOUND=false

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  ok "Anthropic  (ANTHROPIC_API_KEY set)"
  PROVIDER_FOUND=true
else
  warn "Anthropic  (ANTHROPIC_API_KEY not set)"
fi

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  ok "GitHub Models / Copilot  (GITHUB_TOKEN set)"
  PROVIDER_FOUND=true
else
  info "GitHub Models / Copilot  (GITHUB_TOKEN not set)"
fi

if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ok "Gemini  (GEMINI_API_KEY set)"
  PROVIDER_FOUND=true
else
  info "Gemini  (GEMINI_API_KEY not set)"
fi

if [[ "$PROVIDER_FOUND" == "false" ]]; then
  echo ""
  info "No LLM provider configured. Only the 'maes eval' command requires one."
fi

# ─── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  MAES CLI installed successfully!${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo ""
echo -e "${BOLD}Next steps:${NC}"
echo ""
echo -e "  1. ${YELLOW}Open a new terminal${NC} (or source your shell profile)"
echo ""
echo -e "  2. Set up MAES in a project:"
echo -e "     ${BLUE}cd my-project${NC}"
echo -e "     ${BLUE}maes init${NC}         ${YELLOW}# scaffold .maes/${NC}"
echo -e "     ${BLUE}maes sync${NC}         ${YELLOW}# compile context + write adapters${NC}"
echo ""
echo -e "  3. (Optional) Set an LLM provider key for 'maes eval':"
echo ""
echo -e "     ${YELLOW}# Anthropic (default)${NC}"
echo -e "     ${BLUE}export ANTHROPIC_API_KEY=sk-ant-...${NC}"
echo ""
echo -e "     ${YELLOW}# GitHub Models / Copilot${NC}"
echo -e "     ${BLUE}export GITHUB_TOKEN=ghp_...${NC}"
echo ""
echo -e "     ${YELLOW}# Google Gemini${NC}"
echo -e "     ${BLUE}export GEMINI_API_KEY=AIza...${NC}"
echo ""
echo -e "     ${YELLOW}# (optional) Force a specific provider${NC}"
echo -e "     ${BLUE}export MAES_PROVIDER=github   # anthropic | github | gemini${NC}"
echo ""
echo -e "  4. Health check:"
echo -e "     ${BLUE}maes doctor${NC}"
echo ""
