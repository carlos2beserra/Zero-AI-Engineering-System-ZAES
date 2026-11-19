# Zero AI Engineering System (ZAES)

> Context Compiler for AI-Assisted Engineering

AI coding assistants know your code. They don't know your organization.

ZAES compiles architectural decisions, compliance rules, business invariants, and organizational constraints into structured, layered context that Claude Code, Cursor, Continue, Copilot, and Windsurf automatically load — one source of truth, all tools.

---

## Instalação

Existem **dois fluxos** independentes:

- **A. Instalação oficial (corporativa)** — para quem **usa** o ZAES nos projetos.
- **B. Desenvolvimento** — para quem **contribui** com o próprio ZAES.

### A. Instalação oficial (AWS CodeArtifact)

O ZAES é distribuído como pacote Python num repositório privado (formato PyPI) no **AWS
CodeArtifact**. Não é preciso clonar este repositório.

**Pré-requisitos:** Python **3.10+** e AWS CLI configurada.

```bash
# 1. Autenticar na AWS
aws sso login

# 2. Gerar o índice autenticado do CodeArtifact
aws codeartifact login --tool pip --domain <domain> --repository <repository>

# 3. Instalar a CLI isolada (recomendado: pipx ou uv)
pipx install "zaes[all]"          # ou: uv tool install "zaes[all]"

# 4. Conferir
zaes --version
zaes doctor
```

> Distribuições Linux recentes bloqueiam `pip install` no Python do sistema (PEP 668). Use
> `pipx`/`uv tool`, ou um virtualenv.
>
> **Rollback:** `pipx install --force "zaes[all]==X.Y.Z"` (versões publicadas são imutáveis).

### B. Desenvolvimento

Instale a CLI a partir do clone em modo **editável**: alterações no código valem na hora, sem
reinstalar.

```bash
git clone https://github.com/Zerodata/zero-ai-engineering-system.git
cd zero-ai-engineering-system/template/scripts/tools

uv tool install --editable ".[all]"     # CLI `zaes` no PATH (~/.local/bin)
# alternativa: python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,all]"

zaes --version
```

Para rodar os testes, veja [Desenvolvimento](#desenvolvimento).

---

## Configurando o ZAES num projeto

Todos os comandos abaixo rodam **na raiz do projeto que vai usar o ZAES** (não neste repositório).

### 1. Inicializar

```bash
cd ~/caminho/do/seu-projeto
zaes init
```

O `zaes init` é interativo: pergunta nome, descrição e domínio de negócio do projeto. Em seguida
ele cria a pasta `.zaes/` com o `config.yaml`, o `OWNERSHIP.yaml` e os placeholders de
`context/human/`. Também instala os agentes de entrada (`zaes-create`, `zaes-analyze`,
`zaes-context-add`), copia os módulos que o CI precisa para `.zaes/vendor/` e ajusta o
`.gitignore`.

### 2. Escolher o caminho

**Projeto novo — a partir de um Blueprint homologado:**

```bash
zaes blueprint list                 # catálogo (fastapi-api, nestjs-api, nextjs-web, react-spa)
zaes blueprint show nestjs-api      # contrato do Blueprint
```

No assistente de IA, rode `/zaes-create` (Claude Code / Copilot) ou `@zaes-create` (Cursor). O
agente apresenta o catálogo, cria o projeto com as ferramentas oficiais e semeia o contexto da
organização. Para semear só o contexto, sem o scaffold: `zaes blueprint seed <id>`.

**Projeto existente — analisar o codebase:**

No assistente de IA, rode `/zaes-analyze` (Claude Code / Copilot) ou `@zaes-analyze` (Cursor). No
Continue e no Windsurf o agente é carregado automaticamente; basta pedir a análise. O agente lê o
código e preenche `.zaes/context/inferred/` (stack, módulos, padrões e erros que a IA tenderia a
cometer).

### 3. Escrever o contexto do time

Edite os arquivos em `.zaes/context/human/`. São os únicos que o time mantém à mão:

| Arquivo             | Camada                  | O que vai nele                               |
| ------------------- | ----------------------- | -------------------------------------------- |
| `compliance.md`     | 1–2 Compliance/Security | Regras invioláveis (PII, auditoria, LGPD...) |
| `integrations.md`   | 3 Contracts             | Contratos com APIs e times vizinhos          |
| `decisions.md`      | 4 Architecture          | Decisões arquiteturais (DEC-001...)          |
| `business-rules.md` | 5 Domain                | Invariantes de negócio                       |
| `principles.md`     | 6 Engineering           | Padrões do time                              |

Para extrair regras de um texto (ata, ADR, conversa), use o agente `/zaes-context-add`.

### 4. Escolher as ferramentas de IA

Em `.zaes/config.yaml`, deixe em `adapters` só as ferramentas que o time usa:

```yaml
adapters:
  - claude     # CLAUDE.md + .claude/commands/
  - cursor     # .cursor/rules/
  - continue   # .continue/rules/
  - windsurf   # .windsurfrules
  - copilot    # .github/copilot-instructions.md + .github/instructions/
```

### 5. Compilar e validar

```bash
zaes sync              # compila o contexto e gera os adapters na raiz do projeto
zaes validate          # exit 1 se houver conflito não resolvido ou contexto vencido (camadas 1–3)
zaes explain status    # resumo: assertions, guards, conflitos
zaes doctor            # diagnóstico completo
```

Rode `zaes sync` sempre que editar `context/human/`. Os adapters gerados (`CLAUDE.md` etc.) **não
devem ser editados à mão**, porque o próximo sync os sobrescreve.

> **Versione os slash commands.** Se o `.gitignore` ignora `.claude/` inteiro, troque por:
>
> ```gitignore
> .claude/*
> !.claude/commands/
> ```

### 6. (Opcional) Servidor MCP

Permite que o assistente consulte o contexto e verifique guards sob demanda:

```bash
zaes serve --print-mcp-config            # mostra a configuração para cada cliente
zaes serve --write-mcp-config            # grava para claude-code, vscode, cursor-project, continue, windsurf
zaes serve --write-mcp-config cursor-project   # ou só para um cliente
```

### 7. (Opcional) Knowledge graph com graphify

Se o projeto tiver um grafo do [graphify](https://pypi.org/project/graphifyy/) em
`graphify-out/graph.json`, o `zaes sync` adiciona aos adapters uma seção orientando o assistente
a usar `graphify query` antes de grep. O ZAES não roda o graphify, só o detecta.

```bash
graphify update .      # gera/atualiza graphify-out/
zaes sync
zaes doctor            # em "Inferred", confirma que o grafo foi detectado
```

### 8. CI

O `zaes sync` copia os workflows para `.github/workflows/` (sem sobrescrever os que já existem) e
os scripts para `scripts/ci/`. Faça commit deles junto com `.zaes/`.

| Workflow                    | Quando roda               | Precisa de                                    |
| --------------------------- | ------------------------- | --------------------------------------------- |
| `zaes-validate.yml`         | push/PR que muda `.zaes/` | nada (gate obrigatório, sem API key)          |
| `zaes-eval.yml`             | PR                        | chave do provider LLM (ver abaixo)            |
| `zaes-adr-detect.yml`       | PR                        | —                                             |
| `zaes-audit.yml`            | segunda, 09:00 UTC        | opcionais: `ANTHROPIC_API_KEY` (modo `--ai`), `ZAES_TOKEN`, `TEAMS_WEBHOOK_URL` |
| `zaes-metrics.yml`          | segunda, 09:00 UTC        | —                                             |
| `zaes-governance.yml`       | segunda, 09:30 UTC        | —                                             |
| `zaes-context-snapshot.yml` | release publicada         | `ZAES_TOKEN` (opcional)                       |

Configure no repositório (*Settings → Secrets and variables → Actions*):

- **Secrets:** `ANTHROPIC_API_KEY` (padrão) ou `GEMINI_API_KEY`. O `GITHUB_TOKEN` (GitHub
  Models) já vem do Actions. Opcionais: `ZAES_TOKEN` e `TEAMS_WEBHOOK_URL`.
- **Variables:** `ZAES_PROVIDER` (`anthropic`, `github`, `gemini`; sem ela, o provider é detectado
  pela chave presente) e `ZAES_EVAL_BLOCK_ON_POOR=true` para bloquear PRs com avaliação ruim.

A CLI é determinística e não usa LLM. As chaves só são lidas pelos scripts de CI.

### Atualizar a CLI depois

```bash
pipx upgrade zaes      # ou: uv tool upgrade zaes
zaes version           # mostra se o projeto precisa de upgrade
zaes upgrade           # migra .zaes/ para a versão da CLI e roda sync
```

---

## Como funciona

ZAES é um **compiler pipeline de 7 estágios** — não um agent runtime, não um gerador de prompts:

```
.zaes/context/human/*.md     ─┐
.zaes/context/inferred/*.json ─┼→ INGEST → NORMALIZE → DEDUPLICATE → LAYER
                               ┘                                         ↓
                                                                   CONFLICT → UNRESOLVED? → exit 1
                                                                         ↓
                                                                    COMPILE → guards + anti-hallucination
                                                                         ↓
                                                                   ADAPTERS → CLAUDE.md + .cursor/ + etc.
```

### 7 camadas de prioridade

| Layer | Nome         | Arquivo             | Budget                              |
| ----- | ------------ | ------------------- | ----------------------------------- |
| 1     | Compliance   | `compliance.md`     | Hot (≤800t)                         |
| 2     | Security     | `compliance.md`     | Hot (use `layer: 2` no frontmatter) |
| 3     | Contracts    | `integrations.md`   | Hot                                 |
| 4     | Architecture | `decisions.md`      | Warm (≤4000t)                       |
| 5     | Domain       | `business-rules.md` | Warm                                |
| 6     | Engineering  | `principles.md`     | Warm                                |
| 7     | Inferred     | `inferred/*.json`   | Somente leitura                     |

Layer 1 sempre sobrescreve layer 7. Compliance nunca é sacrificada por budget.

---

## CLI

```
zaes init                    # scaffold interativo de .zaes/
zaes sync                    # compila o contexto e gera os adapters (sem LLM)
zaes validate                # gate de CI: exit 1 se inválido
zaes doctor                  # health check
zaes explain status|guard|conflict|context|savings   # auditar decisões do compilador
zaes audit                   # qualidade do contexto (score 0-100); --ai usa LLM
zaes serve                   # servidor MCP (stdio)
zaes blueprint list|show|prompt|bootstrap|seed|validate
zaes agent list|add|remove   # agentes opcionais do catálogo
zaes build-arch-map          # mapa de arquitetura determinístico
zaes inferred-to-canonical   # normaliza o inferred/ produzido pelos agentes
zaes version                 # versão da CLI e do projeto
zaes upgrade                 # migra .zaes/ para a versão atual
```

`zaes <comando> --help` mostra as opções de cada um. `zaes --project-dir PATH <comando>` aponta para
outro projeto em vez de procurar `.zaes/` a partir do diretório atual.

---

## Estrutura deste repositório

```
template/
├── scripts/
│   ├── ci/                  ← scripts chamados pelos workflows
│   ├── hooks/               ← git hooks opcionais (post-commit)
│   └── tools/               ← pacote Python da CLI (zaes/) + testes
└── .github/workflows/       ← 7 workflows de automação

web/                         ← site de documentação (Next.js + Fumadocs)
└── content/docs/            ← documentação em MDX (source of truth)

gitops/zaes-gateway/         ← gateway LLM (LiteLLM) para Kubernetes
```

### .zaes/ (criado nos projetos por `zaes init`)

```
.zaes/
├── config.yaml
├── OWNERSHIP.yaml           ← responsáveis por layer
├── context/
│   ├── human/               ← curado pelo time — editar aqui
│   │   ├── compliance.md    (Layer 1-2)
│   │   ├── integrations.md  (Layer 3)
│   │   ├── decisions.md     (Layer 4)
│   │   ├── business-rules.md (Layer 5)
│   │   └── principles.md    (Layer 6)
│   └── inferred/            ← gerado pelo agente zaes-analyze — nunca editar
├── agents/
├── evals/scenarios/ + results/
├── vendor/zaes/             ← módulos usados pelo CI (atualizado por zaes upgrade)
├── synthesis/               ← gerado por zaes sync — nunca editar
│   ├── assertions.json
│   ├── guards.json
│   ├── anti-hallucination.json
│   ├── conflicts.json
│   └── staleness.json
└── audit/                   ← gerado por zaes audit
    ├── latest-report.md
    └── latest-report.json
```

---

## Documentação

Documentação completa em `web/content/docs/` e publicada em [zaes.zero.io/docs](https://zaes.zero.io/docs).

| Seção            | Conteúdo                                                        |
| ---------------- | --------------------------------------------------------------- |
| Visão Geral      | O que é ZAES, analogia do compilador, arquitetura               |
| Primeiros Passos | Instalação, quickstart, CI setup, guia de adoção                |
| Conceitos        | 7 layers, staleness, pipeline do compilador                     |
| Contexto Humano  | Referência de cada arquivo em .zaes/context/human/              |
| CLI Reference    | Todos os comandos com exemplos de output                        |
| Integrações      | Claude Code, Cursor, Continue, Copilot, Windsurf, graphify, MCP |
| CI/CD            | 7 workflows GitHub Actions                                      |
| Governança       | Staleness policy, OWNERSHIP.yaml                                |
| Evals            | LLM-as-judge, cenários, resultados                              |

---

## Desenvolvimento

### Rodando os testes

Os testes cobrem o pipeline do compilador, os adapters, as políticas de guard, o servidor MCP e o
empacotamento. Não precisam de API key e rodam em poucos segundos.

```bash
cd template/scripts/tools
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,all]"
pytest -q
```

### Fluxo de contribuição

O pipeline é determinístico: edite os módulos em `template/scripts/tools/zaes/`, rode os testes e
execute `zaes sync` num projeto de teste para conferir o que foi gerado. Com a instalação
editável, não é preciso reinstalar a CLI. Releases são disparadas por tag; veja
[docs/RELEASING.md](docs/RELEASING.md).

---

## O que o ZAES não é

- Não é agent runtime — não executa tarefas, só compila contexto
- Não é sistema de documentação — os arquivos de contexto são para a IA, não para humanos
- Não é opinionated sobre stack — funciona com qualquer linguagem ou framework
- Não é substituição para code review — é o que acontece _antes_ da geração

---

## Licença

MIT — use, adapte, contribua.
# Zero-AI-Engineering-System-ZAES-
