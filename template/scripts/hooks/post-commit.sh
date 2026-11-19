#!/usr/bin/env bash
# MAES post-commit hook — lembrete de atualização de contexto
# Install: cp template/scripts/hooks/post-commit.sh .git/hooks/post-commit && chmod +x .git/hooks/post-commit

YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

CHANGED=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || git diff --name-only HEAD 2>/dev/null || true)

if [ -z "$CHANGED" ]; then
  exit 0
fi

PRODUCTION_PATTERNS="^src/|^app/|^api/|^services/|^lib/|^db/migrations/|^internal/|^pkg/|^cmd/"
TOUCHED_CODE=$(echo "$CHANGED" | grep -E "$PRODUCTION_PATTERNS" || true)

if [ -z "$TOUCHED_CODE" ]; then
  exit 0
fi

COMMIT_MSG=$(git log -1 --pretty=%s 2>/dev/null || true)

echo ""
echo -e "${BOLD}${YELLOW}⚡ MAES — Lembrete de Contexto${NC}"
echo -e "${CYAN}Este commit tocou código de produção. Considere atualizar:${NC}"
echo ""

if echo "$COMMIT_MSG" | grep -qiE "^feat|^refactor|^chore.*arch|breaking"; then
  echo -e "  ${YELLOW}→${NC} ${BOLD}.maes/context/human/decisions.md${NC}  (registrar decisão arquitetural)"
fi

if echo "$COMMIT_MSG" | grep -qiE "^feat|^fix|^perf"; then
  echo -e "  ${YELLOW}→${NC} ${BOLD}.maes/context/human/business-rules.md${NC}  (nova regra de domínio?)"
fi

if echo "$COMMIT_MSG" | grep -qiE "^fix.*security|^fix.*auth|^fix.*compliance|security|compliance"; then
  echo -e "  ${YELLOW}→${NC} ${BOLD}.maes/context/human/compliance.md${NC}  (nova restrição de segurança?)"
fi

if ! echo "$COMMIT_MSG" | grep -qiE "^feat|^fix|^perf|^refactor|^chore.*arch|breaking"; then
  echo -e "  ${YELLOW}→${NC} .maes/context/human/decisions.md"
  echo -e "  ${YELLOW}→${NC} .maes/context/human/business-rules.md"
fi

echo ""
echo -e "  ${CYAN}Após editar: execute ${BOLD}maes sync${NC}${CYAN} para recompilar o contexto.${NC}"
echo -e "  ${CYAN}Ignorar se nenhum contexto de negócio foi afetado.${NC}"
echo ""
