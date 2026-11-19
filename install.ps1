# MAES CLI Installer for Windows (PowerShell)
# Usage: git clone https://github.com/Maxxidata/maxxi-ai-engineering-system.git
#        cd maxxi-ai-engineering-system
#        .\install.ps1
#
# Flags:
#   -Editable    Install in editable mode (pip install -e) instead of pipx.
#                Useful for contributors who modify the CLI source.

param(
    [switch]$Editable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Config ────────────────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolsDir  = Join-Path $ScriptDir "template\scripts\tools"

if (-not (Test-Path $ToolsDir)) {
    Write-Error "Error: $ToolsDir not found.`nRun this script from the root of the cloned maxxi-ai-engineering-system repo."
    exit 1
}

# ─── Helpers ───────────────────────────────────────────────────────────────────
function Ok($msg)     { Write-Host "  " -NoNewline; Write-Host "[OK]" -ForegroundColor Green -NoNewline; Write-Host " $msg" }
function Warn($msg)   { Write-Host "  " -NoNewline; Write-Host "[WARN]" -ForegroundColor Yellow -NoNewline; Write-Host " $msg" }
function Info($msg)   { Write-Host "  " -NoNewline; Write-Host "-->" -ForegroundColor Cyan -NoNewline; Write-Host " $msg" }
function Err($msg)    { Write-Host "  " -NoNewline; Write-Host "[FAIL]" -ForegroundColor Red -NoNewline; Write-Host " $msg" }
function Header($msg) { Write-Host "`n$msg" -ForegroundColor White }

# ─── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   MAES — Maxxi AI Engineering System     ║" -ForegroundColor Cyan
Write-Host "║   CLI Installer (Windows)                ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Python 3.9+ ───────────────────────────────────────────────────────────────
Header "Checking prerequisites"

$PythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $PythonCmd = $cmd
        break
    }
}

if (-not $PythonCmd) {
    Write-Error "Python 3.9+ is required. Download from https://python.org and re-run."
    exit 1
}

$PythonVersion = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$PythonMajor   = [int](& $PythonCmd -c "import sys; print(sys.version_info.major)")
$PythonMinor   = [int](& $PythonCmd -c "import sys; print(sys.version_info.minor)")

if ($PythonMajor -lt 3 -or ($PythonMajor -eq 3 -and $PythonMinor -lt 9)) {
    Write-Error "Python $PythonVersion detected. MAES requires Python 3.9+."
    exit 1
}

Ok "Python $PythonVersion (command: $PythonCmd)"

# ─── pipx ──────────────────────────────────────────────────────────────────────
Header "Installing pipx"

if (Get-Command pipx -ErrorAction SilentlyContinue) {
    Ok "pipx already installed ($(pipx --version))"
} else {
    Info "pipx not found — installing..."
    & $PythonCmd -m pip install --user --quiet pipx
    Ok "pipx installed"
}

# Refresh PATH so pipx is available in this session
$UserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
$MachinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
$env:PATH = "$UserPath;$MachinePath"

# Ensure pipx bin dir is in the user PATH registry (pipx ensurepath is unreliable on Windows)
$PipxBinDir = & $PythonCmd -m pipx environment --value PIPX_BIN_DIR 2>$null
if (-not $PipxBinDir) { $PipxBinDir = "$env:USERPROFILE\.local\bin" }

$CurrentUserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
if ($CurrentUserPath -notlike "*$PipxBinDir*") {
    [System.Environment]::SetEnvironmentVariable("PATH", "$CurrentUserPath;$PipxBinDir", "User")
    Info "Added $PipxBinDir to user PATH (registry)"
    $env:PATH = "$env:PATH;$PipxBinDir"
}

# ─── Install MAES ──────────────────────────────────────────────────────────────
Header "Installing maes"

Info "Source: $ToolsDir"

if ($Editable) {
    Info "Mode: editable (pip install -e)"
    & $PythonCmd -m pip install --quiet -e "$ToolsDir[all]"
    if ($LASTEXITCODE -ne 0) { Err "pip install failed"; exit 1 }
    Ok "maes installed in editable mode (anthropic + openai + mcp SDKs ready)"
} else {
    $MaesInstalled = (pipx list 2>$null) -match "package maes "
    if ($MaesInstalled) {
        # Clean uninstall + install avoids the 'uv venv already exists, use --clear'
        # failure that pipx install --force hits on newer uv backends.
        Info "maes already installed — uninstalling previous version..."
        pipx uninstall maes --quiet 2>$null | Out-Null
    }
    pipx install $ToolsDir --quiet
    if ($LASTEXITCODE -ne 0) { Err "pipx install failed"; exit 1 }
    # Inject all optional SDKs: anthropic (Claude), openai (GitHub Models +
    # Gemini OpenAI-compatible endpoint), mcp (required by 'maes serve').
    Info "Injecting LLM provider + MCP SDKs..."
    pipx inject maes anthropic openai mcp --quiet
    if ($LASTEXITCODE -ne 0) { Warn "pipx inject failed — 'maes serve' / eval may not work until you run: pipx inject maes anthropic openai mcp" }
    Ok "maes installed (anthropic + openai + mcp SDKs ready)"
}

# ─── PATH check ────────────────────────────────────────────────────────────────
Header "PATH"

if (-not (Get-Command maes -ErrorAction SilentlyContinue)) {
    Warn "maes not in PATH yet — this is expected on a fresh install."
    Warn "Restart PowerShell, or run:"
    Write-Host ""
    Write-Host '    $env:PATH += ";' + "$env:USERPROFILE\.local\bin" + '"'
    Write-Host ""
    $PathOk = $false
} else {
    Ok "maes is in PATH ($(Get-Command maes | Select-Object -ExpandProperty Source))"
    $PathOk = $true
}

# ─── Validate ──────────────────────────────────────────────────────────────────
if ($PathOk) {
    Header "Validating installation"
    $DoctorOutput = maes doctor 2>$null
    if ($DoctorOutput -match "Python") {
        Ok "maes doctor passed"
    } else {
        Warn "maes doctor reported issues — run 'maes doctor' after setup to review"
    }
}

# ─── Provider check ────────────────────────────────────────────────────────────
Header "LLM provider"

$ProviderFound = $false

if ($env:ANTHROPIC_API_KEY) {
    Ok "Anthropic  (ANTHROPIC_API_KEY set)"
    $ProviderFound = $true
} else {
    Warn "Anthropic  (ANTHROPIC_API_KEY not set)"
}

if ($env:GITHUB_TOKEN) {
    Ok "GitHub Models / Copilot  (GITHUB_TOKEN set)"
    $ProviderFound = $true
} else {
    Info "GitHub Models / Copilot  (GITHUB_TOKEN not set)"
}

if ($env:GEMINI_API_KEY) {
    Ok "Gemini  (GEMINI_API_KEY set)"
    $ProviderFound = $true
} else {
    Info "Gemini  (GEMINI_API_KEY not set)"
}

if (-not $ProviderFound) {
    Write-Host ""
    Info "No LLM provider configured. Only the 'maes eval' command requires one."
}

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  MAES CLI installed successfully!" -ForegroundColor Green
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Restart PowerShell (or run: " -NoNewline
Write-Host 'refreshenv' -ForegroundColor Cyan -NoNewline
Write-Host ")"
Write-Host ""
Write-Host "  2. Set up MAES in a project:"
Write-Host "       cd my-project" -ForegroundColor Cyan
Write-Host "       maes init" -ForegroundColor Cyan -NoNewline
Write-Host "           # scaffold .maes/"
Write-Host "       maes sync" -ForegroundColor Cyan -NoNewline
Write-Host "           # compile context + write adapters"
Write-Host ""
Write-Host "  3. (Optional) Set an LLM provider key for 'maes eval':"
Write-Host ""
Write-Host "       # Anthropic (default)" -ForegroundColor Yellow
Write-Host '       $env:ANTHROPIC_API_KEY = "sk-ant-..."' -ForegroundColor Cyan
Write-Host ""
Write-Host "       # GitHub Models / Copilot" -ForegroundColor Yellow
Write-Host '       $env:GITHUB_TOKEN = "ghp_..."' -ForegroundColor Cyan
Write-Host ""
Write-Host "       # Google Gemini" -ForegroundColor Yellow
Write-Host '       $env:GEMINI_API_KEY = "AIza..."' -ForegroundColor Cyan
Write-Host ""
Write-Host "  4. Health check:"
Write-Host "       maes doctor" -ForegroundColor Cyan
Write-Host ""
