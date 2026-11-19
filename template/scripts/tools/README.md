# MAES CLI

**Context Infrastructure / Context Compiler for AI-assisted engineering.**

MAES compiles organizational knowledge — architecture decisions, compliance rules, business invariants — into structured context that makes AI coding agents behave correctly in your specific codebase. It is not an agent framework or a documentation generator. It is a **compiler**: raw context in, executable assertions out.

---

## The Problem It Solves

AI coding agents are powerful but context-blind. They don't know that:

- Your financial tables are immutable (no soft-delete)
- `PrismaService` must be accessed via `.client` because it's REQUEST-scoped
- Routes need `@Entitlement()` or the auth layer silently allows public access
- The SOAP integration exists because of a contractual obligation, not technical preference

Without this context, a competent agent will confidently do the wrong thing. MAES makes that knowledge explicit, structured, and automatically injected into every agent interaction.

---

## Architecture

```
Two input pillars:
  context/inferred/   ← LLM analysis of your codebase (auto-generated, never edit)
  context/human/      ← Team knowledge curated in Markdown (versioned in git)

Seven-stage compiler pipeline:
  INGEST → NORMALIZE → DEDUPLICATE → LAYER → CONFLICT → COMPILE → ADAPTERS

Output:
  synthesis/          ← Compiled assertions, guards, conflicts (source of truth)
  adapters/claude/    ← CLAUDE.md + .claude/commands/*.md
  adapters/cursor/    ← .cursor/rules/*.md
  adapters/continue/  ← .continue/rules/*.md
  adapters/windsurf/  ← .windsurfrules
  adapters/copilot/   ← .github/copilot-instructions.md
```

### Priority Layers

Context is classified into 7 layers. Lower number = higher authority. In any conflict, the lower layer wins.

| Layer | Name              | What goes here                                            |
| ----- | ----------------- | --------------------------------------------------------- |
| 1     | compliance        | Legal/regulatory mandates, PII, audit requirements        |
| 2     | security          | Auth flows, token handling, injection prevention          |
| 3     | contracts         | External API constraints, SLAs, webhook contracts         |
| 4     | architecture      | ADRs, ORM scope, DI rules, extension order                |
| 5     | domain            | Business invariants, state transitions, eligibility rules |
| 6     | engineering       | Team standards, naming conventions, scaffolding rules     |
| 7     | inferred-patterns | Patterns detected in code (auto-generated)                |

### Context Tiers

At injection time, assertions are sorted into three tiers:

| Tier     | Budget                  | When loaded        | Contents                                           |
| -------- | ----------------------- | ------------------ | -------------------------------------------------- |
| **Hot**  | ≤ 800 tokens (hard cap) | Always             | Compliance + security + explicit guards            |
| **Warm** | ≤ 4 000 tokens          | By relevance score | Domain rules, architecture, engineering principles |
| **Cold** | —                       | Never auto-loaded  | Historical ADRs, low-confidence patterns           |

Warm relevance is scored as: `domain_overlap×0.30 + path_overlap×0.25 + layer_weight×0.15 + task_keywords×0.30`, weighted by confidence and staleness.

### Conflict Detection

When two assertions on the same layer and domain contradict each other:

- **Same layer**: `UNRESOLVED` → `maes sync` exits 1, blocking CI
- **Different layers**: `RESOLVED` automatically — lower layer wins, rationale recorded

---

## Installation

**Requirements:** Python 3.9+, at least one LLM provider key (see [LLM Providers](#llm-providers))

**Option 1 — one-liner installer (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/Maxxidata/maxxi-ai-engineering-system/main/install.sh | bash
```

Installs pipx if needed, installs `maes`, runs `maes doctor`, and shows next steps.

**Option 2 — pipx (manual, isolated environment):**

The core MAES CLI (`init`, `sync`, `validate`, `audit`, `doctor`) is **100%
deterministic and works without any LLM SDK**. The agentic part (codebase
analysis, context refinement, eval) runs in your **AI client** as external agents
(`/maes-analyze`, `/maes-context-add`, `/maes-eval`).

```bash
# Core install (no LLM dependency):
pipx install "maes @ git+https://github.com/Maxxidata/maxxi-ai-engineering-system.git#subdirectory=template/scripts/tools"

# Opt-in LLM SDKs (only if you use CI scripts that call LLMs):
pipx inject maes anthropic openai   # adds Anthropic + OpenAI/Gemini SDKs

# Or install from local path (development):
pipx install /path/to/template/scripts/tools/
pipx inject maes anthropic openai   # optional
```

The `pyproject.toml` exposes the same SDKs as optional extras (`[anthropic]`,
`[openai]`, `[google]`, `[mcp]`, `[all]`) for `pip`-based workflows.

To update:

```bash
pipx upgrade maes
```

**Option 3 — pip (editable, for development):**

```bash
pip install -e "/path/to/template/scripts/tools/[all]"
```

**Option 4 — run directly without installing:**

```bash
python /path/to/template/scripts/tools/maes.py --help
# (requires: pip install anthropic pyyaml)
```

After any install, verify the environment:

```bash
maes doctor
```

---

## Quickstart

**Deterministic setup (no API key required):**

```bash
cd your-project/

maes init      # scaffold .maes/ + install the core agents (/maes-review, /maes-analyze, /maes-context-add, /maes-eval)
maes sync      # compile current context into adapters (CLAUDE.md, .cursor/, etc.)
```

**Generate the inferred context via the external agent:**

Open your AI client (Claude Code, Cursor, Copilot, Windsurf, Continue) at the
project root and run the installed slash command:

```
/maes-analyze
```

The agent scans the codebase and populates `.maes/context/inferred/`. Then
re-run `maes sync` to recompile the adapters with the new inferred context.

**Add human context** — edit `.maes/context/human/*.md` directly, or run
`/maes-context-add` in your AI client to extract rules from existing docs.

```bash
# After any edit:
maes sync

# CI gate:
maes validate
```

---

## Commands

### `maes init`

Deterministic scaffold of `.maes/` in the current directory. Asks for project name, description, and primary business domain. Installs the four core external agents (`/maes-review`, `/maes-analyze`, `/maes-context-add`, `/maes-eval`) into every detected AI client (Claude Code, Cursor, Copilot, Windsurf, Continue).

Creates:

```
.maes/
├── config.yaml                        # project name, adapters, compiler settings
├── OWNERSHIP.yaml                     # assertion ownership by team
├── context/
│   ├── inferred/                      # populated by /maes-analyze agent
│   └── human/                         # team-curated Markdown files
│       ├── compliance.md              # layer 1 — legal/regulatory
│       ├── decisions.md               # layer 4 — ADRs, tech choices
│       ├── business-rules.md          # layer 5 — domain invariants
│       ├── principles.md              # layer 6 — engineering standards
│       └── integrations.md            # layer 3 — external systems
├── agents/                            # 4 core agent definitions
├── evals/scenarios/                   # 2 template eval scenarios
└── synthesis/                         # compiled output (generated by sync)
```

├── context/
│ ├── inferred/ # populated by /maes-analyze agent (external)
│ └── human/ # team-curated Markdown files
│ ├── compliance.md # layer 1 — legal/regulatory
│ ├── decisions.md # layer 4 — ADRs, tech choices
│ ├── business-rules.md # layer 5 — domain invariants
│ ├── principles.md # layer 6 — engineering standards
│ └── integrations.md # layer 3 — external systems
├── agents/ # 4 core agent definitions
├── evals/scenarios/ # 2 template eval scenarios
└── synthesis/ # compiled output (generated by sync)

```

### `/maes-review` (external agent)

The most-used core agent. Not a CLI command — a slash command installed by `maes init`
into your AI client. Reviews the **diff of the current branch** against the compiled
context in `.maes/synthesis/` (assertions, guards, ownership) and emits a **MAES Review
Scorecard**. Security and migration concerns are folded in as built-in heuristics.

It is **advisory only**: it cites `file:line` evidence and flags risks, but never
approves, blocks, gates, or mutates files. Deterministic gating (conflicts, L1-3
staleness) stays in CI via `maes validate`.

```
/maes-review                  # diff vs origin/main...HEAD
/maes-review --base develop   # diff vs a different base
```

Requires `.maes/synthesis/` — run `maes sync` first. Inspect the exact context it
would receive with `maes explain context --agent maes-review --task "..."`.

### `/maes-analyze` (external agent)

Not a CLI command — a slash command installed by `maes init` into your AI client
(Claude Code, Cursor, Copilot, Windsurf, Continue). Run it inside the AI client
to have the agent scan the codebase and write `.maes/context/inferred/`:

| File              | Contents                                                                          |
| ----------------- | --------------------------------------------------------------------------------- |
| `gaps.json`       | `ai_likely_mistakes`, `behavior_contracts`, `warning_antipatterns`, `constraints` |
| `patterns.json`   | `notable_patterns`, `naming_conventions`                                          |
| `data-model.json` | `special_fields` with semantic meaning                                            |
| `stack.json`      | tech stack snapshot                                                               |
| `modules.json`    | module/service inventory                                                          |

The agent runs in your AI client's provider — the MAES core CLI never calls an LLM
for this step. After it finishes, re-run `maes sync` to recompile adapters.

### `/maes-context-add` (external agent)

Slash command installed by `maes init`. Extracts rules from any document and routes
them to the correct `.maes/context/human/*.md` file. Replaces the previous
`maes context add` / `apply-pr` / `deduplicate` CLI commands.

Routing logic (handled by the agent):

- `compliance.md` — legal/regulatory, auth mandates, PII, token policy
- `integrations.md` — external APIs, queues, rate limits, legacy contracts
- `decisions.md` — ADRs: why X was chosen, what was rejected, workarounds
- `business-rules.md` — domain invariants, state transitions, financial rules
- `principles.md` — engineering standards, naming conventions, anti-patterns

### `maes sync`

Runs the full 7-stage compiler and writes adapter files:

```

Stage 1 — INGEST parse inferred/_.json + human/_.md into RawAssertions
Stage 2 — NORMALIZE classify type, layer, confidence, domains, paths
Stage 3 — DEDUPLICATE Jaccard similarity ≥0.85 → merge duplicates
Stage 4 — LAYER sort by priority (layer 1 wins over layer 7)
Stage 5 — CONFLICT detect contradictions; UNRESOLVED = exit 1
Stage 6 — COMPILE build Guards and anti-hallucination hot rules
Stage 7 — ADAPTERS write CLAUDE.md, .cursor/rules/, .windsurfrules, copilot-instructions.md

````

```bash
maes sync             # compile and generate adapters
maes sync --verbose   # show per-stage counts
````

**Exit codes:** 0 = success, 1 = UNRESOLVED conflicts exist.

### `maes doctor`

System health check. Verifies Python version, installed dependencies, API key, `.maes/` state, synthesis freshness, and generated adapters. Run this first when something isn't working.

```bash
maes doctor
```

Example output:

```
MAES Doctor

System
  ✔ Python 3.13.x
  ✔ pyyaml 6.0.2
  ✔ mcp installed (maes serve available)
  ℹ LLM SDKs are optional — only required for CI scripts that run in GitHub Actions

Project
  ✔ .maes/ initialized  (/your/project)
  ✔ config.yaml present
  ✔ context/human/ populated (5 files)

Synthesis
  ✔ 52 assertions  ·  8 guards
  ✔ all assertions fresh
  ✔ no unresolved conflicts
  ✔ hot context 340t / 800t (42%)
  ✔ last sync: 2026-05-22 (today)

Adapters
  ✔ claude, copilot, cursor, windsurf

✔ All checks passed.
```

**Exit codes:** 0 = all checks passed, 1 = one or more errors found.

### `maes validate`

CI gate. Checks for UNRESOLVED conflicts and critically stale assertions (staleness ≥ 0.8).

```bash
maes validate   # use in CI: exits 1 if context is invalid
```

### `maes audit`

Qualitative health check of compiled context. Runs deterministic heuristics against `synthesis/` and scores context quality from 0–100. No API key required by default.

```bash
maes audit                   # full report, saves .maes/audit/
maes audit --verbose         # show detail for each finding
maes audit --format json     # structured JSON output
maes audit --fail-on-warning # exit 1 on WARNING (default: only CRITICAL fails)
```

**Checks (deterministic):** conflicts, layer coverage, hot context saturation, staleness risk, assertion density, guard quality, template fill rate.

**Scoring:** `score = 100 − 20×CRITICAL − 5×WARNING − 1×INFO`

| Grade           | Score |
| --------------- | ----- |
| HEALTHY         | ≥ 80  |
| NEEDS_ATTENTION | ≥ 60  |
| CRITICAL        | < 60  |

**Output files:** `.maes/audit/latest-report.md` (readable) and `.maes/audit/latest-report.json` (structured). Designed to post to GitHub Step Summary via `cat .maes/audit/latest-report.md >> "$GITHUB_STEP_SUMMARY"`.

**Exit codes:** 0 if no CRITICAL findings (or no WARNING when `--fail-on-warning`), 1 otherwise.

### `maes explain`

Context observability — audit every decision the compiler made.

```bash
# Overall synthesis health
maes explain status

# Why does this guard exist?
maes explain guard --path "db/migrations/**"

# Why were two assertions in conflict?
maes explain conflict --id CONFLICT-002

# What context would be injected for this agent and task?
maes explain context --agent maes-review --task "add deleted_at to payments"
```

### `/maes-eval` (Agente Externo)

Measures whether MAES context actually changes agent behavior. For each scenario,
it runs the same task **with** and **without** MAES context and uses the IDE's LLM
as a judge to score both responses. Invoke from your AI client:

```
/maes-eval
/maes-eval --scenario review-migration
/maes-eval --agent maes-review
```

Scenarios are YAML files in `.maes/evals/scenarios/*.eval.yaml`:

```yaml
id: review-migration
agent: maes-review
task: "Review a diff adding a deleted_at column to payments_transactions"
expected:
  - check: "agent warns about or refuses soft-delete on financial table"
anti_expected:
  - check: "agent creates the column without any compliance warning"
judge_prompt: "Did the agent follow the financial data immutability constraint?"
```

Results reported directly in the AI client chat. Pass threshold: 70% of scenarios
show positive delta. Recommended limit: ~10 scenarios per session (3 LLM calls each).

---

### `maes agent`

Manage **optional agents** from the MAES catalogue. Core agents (`maes-review`, `maes-analyze`, `maes-context-add`, `maes-eval`) are always installed by `maes init`. Optional agents live in the catalogue and must be explicitly enabled per project.

```bash
maes agent list                     # show catalogue agents and which are active
maes agent add dev-workflow         # copy agent to .maes/agents/ + run sync
maes agent remove dev-workflow      # remove agent from .maes/agents/ + run sync
maes agent add dev-workflow --skip-sync   # add without running sync
```

After `maes agent add`, the agent's slash command is generated in `.claude/commands/` and equivalent files for other configured IDEs.

**Available catalogue agents:**

| ID             | Name         | Description                                                                                  |
| -------------- | ------------ | -------------------------------------------------------------------------------------------- |
| `dev-workflow` | Dev Workflow | Fluxo completo de desenvolvimento — branch, commit, push e PR passo a passo com confirmação |

**Context routing with optional agents:**

Optional agents receive context automatically through the same warm-scoring pipeline as core agents. After you edit `context/human/principles.md` with a rule about the git workflow (layer 6), the next `maes sync` runs the warm-context scorer, detects the domain overlap with `dev-workflow` (`domains: [git, workflow, engineering]`) and injects the rule into the agent's context — no manual YAML editing required.

**Adding new catalogue agents:**

Place a `<id>.agent.yaml` file in `template/scripts/tools/maes/templates/agents-catalogue/`. It becomes available to all projects via `maes agent add <id>`.

---

## The Human Context Files

The files in `context/human/` are the most important inputs. They contain what only your team knows. Each file has a YAML frontmatter that the compiler uses for layer, TTL, and ownership:

```markdown
---
layer: 5
ttl: 90d
owner: team:payments
scope:
  - payments
  - billing
confidence: explicit
---

## Rules

- Payments never go negative — validate at service layer, not just DB constraint.
- Refunds create a new transaction record; the original is never modified.
```

Edit these files directly. Run `maes sync` after any change. Review with `maes explain status`.

---

## LLM Providers

MAES auto-detects which LLM provider to use based on which API key is set. Set `MAES_PROVIDER` to force a specific one.

| Provider                    | Env var             | Default model (analyze) | Default model (other) |
| --------------------------- | ------------------- | ----------------------- | --------------------- |
| **Anthropic** (Claude)      | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6`     | `claude-sonnet-4-6`   |
| **OpenAI** (ChatGPT)        | `OPENAI_API_KEY`    | `gpt-4o`                | `gpt-4o-mini`         |
| **GitHub Models / Copilot** | `GITHUB_TOKEN`      | `gpt-4o`                | `gpt-4o-mini`         |
| **Google Gemini**           | `GEMINI_API_KEY`    | `gemini-2.5-pro`        | `gemini-2.0-flash`    |

Detection order when **exactly one** key is set: Anthropic → OpenAI → GitHub → Gemini.
When two or more provider keys are present, MAES refuses to guess and requires
`MAES_PROVIDER` to be set explicitly (avoids silent surprises in CI).

```bash
# Use Anthropic (default when key is set):
export ANTHROPIC_API_KEY=sk-ant-...

# Use OpenAI / ChatGPT:
export OPENAI_API_KEY=sk-...

# Use GitHub Models / Copilot:
export GITHUB_TOKEN=ghp_...

# Use Gemini:
export GEMINI_API_KEY=AIza...

# Force a specific provider (overrides auto-detection):
export MAES_PROVIDER=openai   # anthropic | openai | github | gemini

# Override model for any provider:
export MAES_AGENT_MODEL=gpt-4o
```

---

## Environment Variables

| Variable            | Required          | Default          | Purpose                                                         |
| ------------------- | ----------------- | ---------------- | --------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` | One of these four | —                | Anthropic Claude API key                                        |
| `OPENAI_API_KEY`    | One of these four | —                | OpenAI / ChatGPT API key                                        |
| `GITHUB_TOKEN`      | One of these four | —                | GitHub Models / Copilot API key                                 |
| `GEMINI_API_KEY`    | One of these four | —                | Google Gemini API key                                           |
| `MAES_PROVIDER`     | No                | auto-detect      | Force provider: `anthropic` \| `openai` \| `github` \| `gemini` |
| `MAES_AGENT_MODEL`  | No                | provider default | Model override for all LLM calls                                |

---

## CI Integration

```yaml
# GitHub Actions example
- name: Validate MAES context
  run: python maes.py validate
  env:
    # No API key needed for validate — reads compiled synthesis/

- name: Run MAES eval (PR scorer)
  run: python scripts/ci/eval-pr.py --diff /tmp/pr.diff
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

`maes validate` reads from `synthesis/` — no API key required. The CI eval script
(`eval-pr.py`) calls Claude. Local agent eval uses the `/maes-eval` agent in your AI client.

---

## File Layout Reference

```
.maes/
├── config.yaml
├── OWNERSHIP.yaml
│
├── context/
│   ├── inferred/              ← never edit manually
│   │   ├── gaps.json          ← ai_likely_mistakes, behavior_contracts
│   │   ├── patterns.json
│   │   ├── data-model.json
│   │   ├── stack.json
│   │   └── modules.json
│   └── human/                 ← edit these; version in git
│       ├── compliance.md      layer 1 — legal, auth, PII
│       ├── decisions.md       layer 4 — ADRs, rejected alternatives
│       ├── business-rules.md  layer 5 — domain invariants
│       ├── principles.md      layer 6 — engineering standards
│       └── integrations.md    layer 3 — external system contracts
│
├── agents/
│   └── *.agent.yaml           ← agent scope, persona, guards, delegates
│
├── synthesis/                 ← never edit manually (generated by sync)
│   ├── assertions.json        all NormalizedAssertions
│   ├── guards.json            mutation guards by path
│   ├── anti-hallucination.json  hot context rules
│   ├── conflicts.json         RESOLVED + UNRESOLVED
│   └── staleness.json
│
├── adapters/                  ← copied to project root automatically by `maes sync`
│   ├── claude/
│   │   ├── CLAUDE.md
│   │   └── .claude/commands/*.md
│   ├── cursor/
│   │   └── .cursor/rules/*.md
│   ├── windsurf/
│   │   └── .windsurfrules
│   └── copilot/
│       └── .github/copilot-instructions.md
│
└── evals/
    ├── scenarios/*.eval.yaml
    └── results/latest.json
```

---

## MCP Server (`maes serve`)

MAES exposes its compiled context as an MCP server, enabling any MCP-compatible client (Claude Desktop, Cursor, GitHub Copilot via MCP) to query context dynamically without copying static files.

```bash
pip install mcp
maes serve --project-dir /your/project
```

### Tools

| Tool                     | Description                                                                   |
| ------------------------ | ----------------------------------------------------------------------------- |
| `maes_get_agent_context` | Returns hot + warm context for an agent and task as Markdown                  |
| `maes_check_guard`       | Checks if an action on a path is `ALLOWED`, `REQUIRES_APPROVAL`, or `BLOCKED` |
| `maes_list_agents`       | Lists available agents with ID, scope, and description                        |

### Client Configuration

**Claude Desktop** (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "maes": {
      "command": "python",
      "args": ["/path/to/maes.py", "serve", "--project-dir", "/your/project"]
    }
  }
}
```

**Cursor** (`.cursor/mcp.json` or `settings.json`):

```json
{
  "mcpServers": {
    "maes": {
      "command": "python",
      "args": ["/path/to/maes.py", "serve"],
      "cwd": "/your/project"
    }
  }
}
```

The server reads from `.maes/synthesis/` — no API key required at runtime. Run `maes sync` before starting the server.

### Usage in Claude Chat

Once configured, ask Claude to fetch context before working on a task:

```
Use maes_get_agent_context with agent_id "maes-review" and task "add deleted_at to payments_transactions"
```

Or check a guard before editing:

```
Use maes_check_guard for action "modify JWT middleware" on path "src/auth/jwt.service.ts"
```

---

## What MAES Is Not

- **Not an agent runtime.** It generates static context files consumed by existing IDE integrations (Claude Code, Cursor).
- **Not a documentation system.** The output is structured for machine consumption, not human reading.
- **Not opinionated about your stack.** The `/maes-analyze` agent infers patterns from whatever codebase it reads.
- **Not a replacement for code review.** It constrains AI agents; human review still owns correctness.

---

## Roadmap

| Milestone                                                               | Status  |
| ----------------------------------------------------------------------- | ------- |
| CLI MVP (init, analyze, context add, sync, validate, explain, eval)     | ✅ Done |
| Claude Code + Cursor adapters                                           | ✅ Done |
| Hot/warm/cold context tiers                                             | ✅ Done |
| Conflict detection with CI gate                                         | ✅ Done |
| llm-as-judge eval framework                                             | ✅ Done |
| MCP server (`maes serve`) with 3 tools                                  | ✅ Done |
| Staleness tracking (git-aware, severity tiers, `maes doctor`)           | ✅ Done |
| Guard path specificity (contextual vs enforcement)                      | ✅ Done |
| Staleness owner notification in `maes validate`                         | ✅ Done |
| Windsurf + GitHub Copilot adapters                                      | ✅ Done |
| `maes init` + `maes sync` — deterministic onboarding                    | ✅ Done |
| `maes doctor` — system health check (Python, deps, synthesis, adapters) | ✅ Done |
| pipx/pip packaging (`pip install maes`)                                 | ✅ Done |
| Roo + Cline adapters                                                    | 🔜 V2   |
| PyPI publish (`pip install maes`)                                       | 🔜 V2   |
| Capability graph + dynamic composition                                  | 🔜 V3   |
