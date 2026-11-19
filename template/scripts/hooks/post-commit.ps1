# MAES post-commit hook — lembrete de atualização de contexto (PowerShell)
# Install: cp template/scripts/hooks/post-commit.ps1 .git/hooks/post-commit.ps1

$Changed = git diff --name-only HEAD~1 HEAD 2>$null
if (-not $Changed) {
    $Changed = git diff --name-only HEAD 2>$null
}

if (-not $Changed) { exit 0 }

$ProductionPatterns = @("^src/", "^app/", "^api/", "^services/", "^lib/", "^db/migrations/", "^internal/", "^pkg/", "^cmd/")

$TouchedCode = $Changed | Where-Object {
    $file = $_
    $ProductionPatterns | Where-Object { $file -match $_ }
}

if (-not $TouchedCode) { exit 0 }

$CommitMsg = git log -1 --pretty=%s 2>$null

Write-Host ""
Write-Host "⚡ MAES — Lembrete de Contexto" -ForegroundColor Yellow
Write-Host "Este commit tocou código de produção. Considere atualizar:" -ForegroundColor Cyan
Write-Host ""

$isArchChange = $CommitMsg -match "^feat|^refactor|^chore.*arch|breaking"
$isDomainChange = $CommitMsg -match "^feat|^fix|^perf"
$isSecurityFix = $CommitMsg -match "^fix.*security|^fix.*auth|^fix.*compliance|security|compliance"
$showAll = -not ($isArchChange -or $isDomainChange -or $isSecurityFix)

if ($isArchChange -or $showAll) {
    Write-Host "  -> .maes/context/human/decisions.md  (registrar decisão arquitetural)" -ForegroundColor Yellow
}
if ($isDomainChange -or $showAll) {
    Write-Host "  -> .maes/context/human/business-rules.md  (nova regra de domínio?)" -ForegroundColor Yellow
}
if ($isSecurityFix) {
    Write-Host "  -> .maes/context/human/compliance.md  (nova restrição de segurança?)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Após editar: execute 'maes sync' para recompilar o contexto." -ForegroundColor Cyan
Write-Host "  Ignorar se nenhum contexto de negócio foi afetado." -ForegroundColor Cyan
Write-Host ""
