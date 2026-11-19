# Scripts MAES

> Automações CI e ferramentas de suporte do framework.

---

## Estrutura

```
scripts/
├── ci/             # Scripts chamados pelos .github/workflows/
│   ├── _provider.py             (abstração LLM — Anthropic / OpenAI / GitHub / Gemini)
│   ├── eval-pr.py               (LLM-as-judge para PRs)
│   ├── collect-metrics.py       (métricas semanais via GitHub API)
│   ├── governance-report.py     (dashboard de saúde do contexto)
│   ├── detect-adr-triggers.py   (detecção de mudanças arquiteturais)
│   ├── context-snapshot.py      (métricas de síntese por release)
│   └── pr_comment.py            (utilitário — posta comentário no PR)
│
├── hooks/          # Git hooks opcionais
│   ├── post-commit.sh           (Unix/Mac — lembrete de contexto pós-commit)
│   └── post-commit.ps1          (Windows PowerShell)
│
├── tools/          # MAES CLI (instalável via pipx)
│   ├── maes/                    (pacote Python — maes init/analyze/sync/eval...)
│   ├── pyproject.toml           (metadata do pacote)
│   └── README.md                (documentação completa do CLI)
│
└── requirements.txt   # Dependências Python para scripts de CI
```

---

## CI (scripts/ci/)

Scripts executados automaticamente pelos workflows em `.github/workflows/`.

### `eval-pr.py` — LLM-as-judge

```bash
python scripts/ci/eval-pr.py --diff pr.diff --task .maes/tasks/TASK-042.md
python scripts/ci/eval-pr.py --diff pr.diff --output comment --post-to-github
```

**Variáveis:** `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY` ou `GITHUB_TOKEN` ou `GEMINI_API_KEY`, `GH_TOKEN`, `GITHUB_REPOSITORY`, `PR_NUMBER`

### `collect-metrics.py` — Métricas semanais

```bash
python scripts/ci/collect-metrics.py --repo org/projeto --days 7 --output markdown
python scripts/ci/collect-metrics.py --repo org/projeto --days 30 --output json
```

### `governance-report.py` — Dashboard de saúde

```bash
python scripts/ci/governance-report.py                    # markdown
python scripts/ci/governance-report.py --output json      # JSON
python scripts/ci/governance-report.py --archive-decisions
```

---

## Hooks (scripts/hooks/)

Git hooks opcionais para lembrar desenvolvedores de atualizar contexto após commits.

```bash
# Instalar (Unix/Mac)
cp scripts/hooks/post-commit.sh .git/hooks/post-commit
chmod +x .git/hooks/post-commit

# Instalar (Windows)
cp scripts/hooks/post-commit.ps1 .git/hooks/post-commit.ps1
```

Após commits que tocam código de produção, o hook sugere quais arquivos de `.maes/context/human/` atualizar.

---

## CLI (scripts/tools/)

Documentação completa: `scripts/tools/README.md`

Instalação rápida:

```bash
# Opção 1 — one-liner (recomendado)
curl -fsSL https://raw.githubusercontent.com/Maxxidata/maxxi-ai-engineering-system/main/install.sh | bash

# Opção 2 — pipx
pipx install "git+https://github.com/Maxxidata/maxxi-ai-engineering-system.git#subdirectory=template/scripts/tools"
pipx inject maes anthropic openai
```

---

## Dependências CI

```bash
pip install -r scripts/requirements.txt
```

Scripts em `ci/` suportam Anthropic, OpenAI, GitHub Models/Copilot e Gemini via `_provider.py`. Encerram sem erro se nenhum provider estiver configurado.
