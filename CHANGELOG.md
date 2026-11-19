# Changelog

Todas as mudanças notáveis neste projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## v1.4.0 — 2026-08-03

Blueprint como Contrato Inicial de Engenharia, correção da causa-raiz do Analyze, e a distribuição
via CodeArtifact que a v1.3.0 documentou sem chegar a publicar.

> **Nota.** A v1.3.0 foi carimbada no código e no CHANGELOG, mas **nunca foi publicada** — não há
> tag `v1.3.0`, nem release notes, nem sincronização no `web/`. O conteúdo dela vai nesta release,
> que portanto acumula tudo entre a v1.2.0 e hoje. Notas técnicas completas em
> [docs/releases/v1.4.0.md](docs/releases/v1.4.0.md).

### Recursos — Blueprint como Contrato Inicial de Engenharia

- **O Blueprint deixa de ser catálogo e passa a ser contrato inicial de engenharia** de um projeto
  novo ([RFC 0001](docs/rfc/0001-blueprint-como-contrato-inicial-de-engenharia.md)). O valor não é
  geração de código — isso continua com as ferramentas oficiais de cada ecossistema (*Official
  First*) — e sim a transferência de conhecimento arquitetural organizacional no nascimento do
  projeto: convenções, boundaries, *intended placement*, nomenclatura, decisões e padrões de teste.
  Sem isso, a IA tinha stack e bootstrap mas perdia o que sustenta o padrão ao longo dos meses, e não
  sabia responder "onde crio um módulo Financeiro?".
- **Cinco ADRs novas** sustentam a RFC: [0003](docs/adr/0003-context-ownership-principle.md) Context
  Ownership Principle · [0004](docs/adr/0004-observed-vs-intended-placement.md) Observed × Intended
  Placement + Divergence Visibility · [0005](docs/adr/0005-autoridade-normativa-observacional.md)
  autoridade normativa × observacional (substitui "humano vence") ·
  [0006](docs/adr/0006-upgrade-de-contrato-blueprint.md) upgrade de contrato + proveniência ·
  [0007](docs/adr/0007-enforcement-ownership.md) Enforcement Ownership ("the Compiler is not an
  architect").
- **Catálogo com 4 Blueprints homologados** — `fastapi-api`, `nestjs-api`, `nextjs-web` e
  `react-spa`, cada um por engenharia reversa curada de um projeto real. Os padrões agnósticos
  levantados no `nextjs-web` foram replicados no `react-spa`, e o teste de `blueprint list` exige os
  quatro: o catálogo não encolhe sem quebrar a suíte.
- **Bootstrap sobrevive ao gate de build scripts do pnpm 10+.**

### Recursos — distribuição corporativa (conteúdo da v1.3.0, agora publicado)

- **Instalação via `pip install maes[all]`** a partir do AWS CodeArtifact (formato PyPI privado): o
  MAES passa a ser instalável sem clonar o repositório.
- **Flag global `maes --version`**, pipeline de release por tag `v*` (`build → validate → publish`
  com guard de versão e OIDC), `build-check` em todo PR e testes de empacotamento validando o
  conteúdo real do wheel e do sdist.
- **`pyproject.toml` com versão dinâmica** a partir de `maes/__init__.py` (fonte única); launcher
  legado `maes.py` removido, pois sombreava o package e quebrava `python -m build`.

### Correções — Analyze

Correção da causa-raiz de um mapa de arquitetura que **encolhia** conforme o projeto crescia
(49 → 22 nós em rodadas consecutivas do mesmo repositório) e de um Observed Placement que
afirmava convenção sem evidência que a sustentasse. Formalizado em
[ADR 0009](docs/adr/0009-observacao-exige-populacao-conhecida.md); investigação em
[findings-discovery-sampling-e-placement-confidence.md](docs/development/findings-discovery-sampling-e-placement-confidence.md).

- **`.tsx`, `.jsx`, `.vue` e `.svelte` eram invisíveis ao Stage 1.** As extensões não constavam
  em `_SOURCE_EXTENSIONS`, e como o BFS de fontes e a detecção de entidades filtram por esse
  conjunto, um projeto React/Next não tinha **nenhum** arquivo elegível fora de
  `_PRIORITY_FILES`. "Zero nós de frontend" era um filtro, não orçamento esgotado. Agora existe
  um único `CANONICAL_SOURCE_EXTENSIONS` em `models.py`, consumido por Stage 1 e `arch_analysis`
  — a divergência entre as duas listas **era** o bug.
- **Cobertura auto-referente.** `files_total` vinha da própria amostra truncada em 200k chars,
  então a métrica era estruturalmente incapaz de revelar sub-amostragem (reportava 60,5% sobre
  43 arquivos num projeto de 848). O denominador passa a ser a população real do projeto.
- **`_PRIORITY_FILES` só era resolvido na raiz.** Em workspace multirepo nenhum `package.json`
  era encontrado e `is_frontend_project` saía `false` por ausência de evidência. Agora manifestos
  são coletados em subprojetos (profundidade ≤ 2), ordenados por prioridade de tipo de manifesto,
  e `_detect_frontend_framework` casa por **basename**.
- **`_collect_auth_models` podia coletar de diretórios ignorados** — ao contrário dos demais
  coletores, não chamava `_in_ignored`, então `.venv/**/models/user.py` entrava como modelo de
  domínio do projeto.
- **A reserva de 40% do orçamento para código não era garantida.** Coleta de auth/domain models
  era isenta do cap da fase de prioridade e podia consumir até ~480k chars (40 arquivos × 12k),
  zerando o BFS de fontes. Agora o `_Collector` tem soft limit e a fase inteira respeita os 60%.
- **Ordenação dependente do SO.** A enumeração ordenava objetos `Path`, cuja comparação no
  Windows é case-insensitive — a mesma árvore produzia ordens diferentes entre plataformas, e
  como o orçamento corta a coleta no meio, a ordem decide *quais* arquivos são lidos. Passa a
  ordenar as strings relativas-posix.
- **Observed Placement afirmava convenção sem lastro.** `_dominant_prefix` somava cada nó também
  no prefixo de 1 segmento, então quando todos compartilhavam a raiz o resultado era 100% →
  confiança `high` → renderizado **sem** aviso no `CLAUDE.md`. Em campo saiu
  `Service → <raiz do repositório> (100%)`, orientando onde colocar código novo.

### Mudanças

- **`architecture_map.json` schema 2.0 → 2.1.** A semântica das métricas de cobertura muda (o
  denominador passa a ser a população, não a amostra) e duas chaves do funil são renomeadas:
  `discovered_files` → `source_files` e `total_nodes` → `node_count`. "Discovered" era lido como
  "o que o collector achou", precisamente a interpretação que produziu o bug do denominador.
- **Novos campos observáveis**: `sampling_ratio` e `sampled_files` (evidência × população),
  `files_sampled` por nó (`file_count` × `files_sampled` é o par população/evidência — um
  `files_sampled: 0` significa que todo campo semântico daquele nó está sem evidência, não que
  esteja vazio), o **Structural Transformation Funnel**
  (`source_files → candidate_count → collapsed_count → node_count`) e os contadores
  `project_roots_discovered` / `analyzed` / `truncated`.
- **`placement-map.json` schema 1.0 → 1.1**, com status distintos por causa: `generated`,
  `no_observed_convention` (observei e não há convenção — diferente de falta de dados),
  `stale_schema`, `invalid_artifact`, `unsupported_schema` e `empty`. Versão desconhecida nunca
  degrada em silêncio.
- **Refusal-to-emit fail-closed, com a evidência certa para cada tipo de afirmação.** Afirmação
  derivada de **estrutura** (onde vive um Service?) exige topologia construída sobre a população,
  o que o `schema_version` responde; afirmação derivada de **conteúdo** (`entry_points`,
  `dep_edges`) exige `sampling_ratio`. As duas políticas vivem em `sampling_policy.py`, separadas
  do mecanismo de emissão. Validando em campo, gatear o placement por amostragem de conteúdo
  suprimia cinco observações válidas num projeto de 941 arquivos que lê 3% do conteúdo dentro do
  orçamento — condição normal e permanente em projetos grandes.
- **`build-arch-map` não coleta mais documentação** (`skip_existing_docs=True`): docs não
  contribuem para topologia e competiam pelo orçamento de conteúdo de um mapa zero-LLM.
- **Enumeração única**: `scan_project()` é a fonte única de verdade para enumeração estrutural,
  consumida por todos os coletores do Stage 1 — antes havia dois `rglob` completos mais 36 globs
  recursivos.

### Atualização

O fluxo oficial absorve a mudança sem intervenção manual:

```bash
maes upgrade          # a seção Code Placement fica OMITIDA — estado seguro
maes build-arch-map   # regenera o mapa em schema 2.1
maes sync             # Code Placement volta, agora com lastro
```

Após `maes upgrade` o `sync` interno lê um mapa em schema anterior, que não declara amostragem;
pelo fail-closed a seção é **omitida** em vez de reemitida errada, e o comando informa o próximo
passo. `maes doctor` sinaliza schema desatualizado. Nenhuma migração é necessária —
`context/inferred/` e `synthesis/` são integralmente regenerados.

---

## v1.3.0 — 2026-07-11

Distribuição oficial do MAES como pacote Python via **AWS CodeArtifact** (formato PyPI
privado). O MAES passa a ser instalável sem clonar o repositório.

### Recursos

- **Instalação corporativa via `pip install maes[all]`** a partir do AWS CodeArtifact.
  Fluxo oficial: `aws sso login` → `aws codeartifact login --tool pip …` →
  `pip install maes[all]`. Documentado no README e em [`docs/RELEASING.md`](docs/RELEASING.md).
- **Flag global `maes --version`** (além do subcomando `maes version`).
- **Pipeline de release** (`.github/workflows/release.yml`) disparado por tag `v*`, com
  jobs encadeados `build → validate → publish`: guard de versão, build reproduzível em
  Python 3.11, instalação do wheel em ambiente limpo + smoke test, e publicação no
  CodeArtifact via OIDC (sem access key fixa). Publicação só após validação.
- **`build-check` no CI** — em todo PR, constrói o wheel, instala em venv isolado e roda
  smoke (`--version`, `blueprint list`, `init --help`), garantindo que o artefato publicado
  realmente funciona.
- **Testes de empacotamento** (`tests/test_packaging.py`) validam conteúdo real do wheel e
  do sdist (templates, agents, blueprints, `bootstrap/`/`context/`), METADATA e o entrypoint
  console-script.

### Mudanças

- **`pyproject.toml`**: versão **dinâmica** a partir de `maes/__init__.py` (fonte única),
  `include-package-data`, metadata completa (license, authors, urls, keywords) e `LICENSE`
  proprietário. Templates continuam empacotados via `package-data` + `MANIFEST.in`.
- **Removido o launcher legado `maes.py`** — o módulo top-level sombreava o package `maes/`
  e quebrava `python -m build` (a versão dinâmica não resolvia). O entrypoint oficial
  (`maes.__main__:main`) já o tornava obsoleto.

### Documentação

- ADR [`0002-distribuicao-via-codeartifact.md`](docs/adr/0002-distribuicao-via-codeartifact.md):
  CodeArtifact como registry oficial, PyPI privado como canal único, wheel como artefato,
  nome congelado (`maes`), versionamento único + SemVer, OIDC, upstream PyPI e governança
  de versões (imutáveis; rollback via pip).

---

## v1.2.0 — 2026-06-05

Modo ad-hoc do `/maes-eval` formalizado e `maes upgrade` passa a atualizar os agents do framework.

### Recursos

- **`/maes-eval` aceita tarefa em texto livre (modo ad-hoc) como caminho de primeira classe.**
  Em um projeto já configurado, `/maes-eval corrigir responsividade da tela de pipeline`
  roda direto — o agent monta um cenário único na hora, derivando `expected`/`anti_expected`
  das regras relevantes do contexto compilado, **sem exigir nenhum `.eval.yaml`**. Os
  cenários `.eval.yaml` continuam suportados, agora como opção para avaliação repetível
  (CI/regressão). Formalizado no `maes-eval.agent.yaml` (agent v1.1.0): novo "Passo 0 —
  Detectar modo", "Passo 2b — Construir cenário ad-hoc" e `argument_hint` atualizado.

### Mudanças

- **`maes upgrade` agora sobrescreve os agents `maes-*` em vez de fazer merge.** Os agents
  do framework (`maes-analyze`, `maes-review`, `maes-context-add`, `maes-eval`) são
  refrescados a partir do template em todo upgrade, garantindo que mudanças nos agents
  (como o modo ad-hoc) cheguem aos projetos existentes. Agents fora do namespace `maes-`
  (ex.: catálogo `dev-workflow` e agents customizados) mantêm o comportamento de merge.
  Tradeoff: customizações manuais em um `.agent.yaml` `maes-*` são sobrescritas no upgrade.

### Documentação

- `reference/prompts.mdx` e a página do agent passam a posicionar o texto livre como uso
  normal e os cenários como opcional; o modo ad-hoc deixa de ser descrito como "best-effort"
  e passa a "modo suportado".

---

## v1.1.4 — 2026-06-05

Release de correções na documentação web (Fumadocs) — **sem mudança de comportamento do CLI**.

### Correções

- **Comando CLI fantasma `maes eval` removido da documentação**: a doc descrevia um
  comando `maes eval` que não existe no core CLI. A avaliação por cenários é feita
  pelo agent `/maes-eval` (usa o LLM do cliente, sem API key); a avaliação de PR em
  CI é feita pelo script `eval-pr.py` (rubric, requer API key). Todas as ~40
  referências em 12 páginas foram corrigidas para apontar para o mecanismo real.
- **Schema de cenário de eval corrigido**: a doc usava `expected_behavior`/`context_file`,
  que não existem. Alinhado ao schema real (`expected`/`anti_expected`/`judge_prompt`),
  o mesmo que `maes init` gera e que o agent `/maes-eval` lê.
- **Dois mecanismos de eval separados**: a doc conflava o eval por cenários
  (agent, WITH/WITHOUT, delta) com o eval de PR em CI (rubric, score 0–14). Agora
  estão explicitamente distintos em `reference/prompts.mdx` e na página do agent.
- **Acoplamento fictício "TASK = cenário de eval" desfeito** em `task-format.mdx` e
  `conventions.mdx`: task files alimentam `maes explain context --task` e o eval de
  PR (`eval-pr.py --task`); cenários são arquivos `.eval.yaml` separados.

### Documentação

- **Uso ad-hoc do `/maes-eval` documentado**: passar uma task em texto livre
  (ex.: `/maes-eval corrigir responsividade da tela de pipeline`) faz o agent montar
  um cenário ad-hoc na hora. Documentado em `reference/prompts.mdx` e na página do
  agent, marcado explicitamente como **best-effort** (não faz parte do contrato
  formal do agent — para avaliação repetível, escreva um `.eval.yaml`).

---

## v1.1.3 — 2026-06-05

Release de correções na documentação web (Fumadocs) — **sem mudança de comportamento do CLI**.

### Correções

- **Busca da documentação não retornava resultados**: o site usa `output: "export"`
  (HTML estático), mas faltava o backend de busca. Adicionada a rota estática
  `web/src/app/api/search/route.ts` (`staticGET` + `revalidate = false`) que emite
  o índice Orama no build, e o `RootProvider` passou a usar o client de busca
  estático (`search={{ options: { type: "static" } }}`) — a busca agora roda
  no navegador sobre o índice gerado.
- **Botão "Instalar agora" invisível no CTA**: a variante `outline` do `Button`
  define `bg-background` (branco), que sobre o gradiente do CTA deixava o botão
  branco com texto branco — só visível no hover. Adicionado `bg-transparent` ao
  botão, deixando o gradiente aparecer atrás do texto.

---

## v1.1.2 — 2026-06-04

Release de documentação e qualidade de código — **sem mudança de comportamento do CLI**.

### Documentação

- **Reposicionamento em torno de Context Governance**: a documentação passa a
  tratar agentes como **consumidores** do contexto governado, não como o produto
  (`Context → Compiler → MCP → Governance`).
  - `foundations/why-maes-exists.mdx` — reescrita com a tese "MAES é uma plataforma
    de Context Governance, não de agentes".
  - `foundations/agent-engineering.mdx` — rebaixado de disciplina foundational a
    camada fina de consumo; exemplo `revisor-seguranca` → `tech-writer`; agentes
    core linkados.
  - `advanced/roadmap.mdx`, `agents/catalog.mdx`, `agents/fixed-agents.mdx` —
    review/segurança/migração apontam para o `/maes-review`.
- **README do CLI** — nova seção do `/maes-review`; `maes init` descrito
  instalando os quatro agentes core; contagem de agentes corrigida; catálogo de
  agents opcionais corrigido (`git-guide` → `dev-workflow`).
- **Invocação por cliente corrigida** em todas as páginas (catálogo, páginas
  por-agente, quick-start, CLI reference/overview) e no output do `maes init`:
  apenas o Claude Code expõe slash command por agente; no Cursor o contexto é uma
  rule auto-aplicada por glob (`.cursor/rules/`) e no Copilot são instruções
  auto-aplicadas (`.github/instructions/`) — não há `@maes-*`/`/maes-*` nesses
  clientes.
- `quick-start.mdx` — a saída de exemplo de `maes init` lista os quatro agentes
  core (revelando o `/maes-review` no primeiro contato).

### Adicionado

- **Página dedicada do `/maes-review`** (`agents/maes-review.mdx`), incluída na
  navegação (`agents/meta.json`) e no catálogo de agentes.

### Correções / Refactor

- **SonarLint smells no CLI** (`maes/__main__.py`, `maes/compiler.py`), todos
  preservando comportamento:
  - S1192 — constante `_CONFIG_FILE` para o literal `"config.yaml"`.
  - S3516 — `_print_mcp_config` retorna `None` (o chamador conduz o `sys.exit`).
  - S3776 — `_write_mcp_config` dividido em `_load_mcp_settings` /
    `_merge_mcp_server_entry` / `_dump_mcp_settings` / `_print_mcp_reload_hint`.
  - S3776 — `_parse_human_assertions` dividido em `_resolve_human_confidence` /
    `_human_assertions_from_file`.
- Versão do agente `maes-review.agent.yaml` alinhada para `1.1.0`.

---

## v1.0.0 — 2026-06-03

> **BREAKING RELEASE** — consolidação MAES v0.16 → v1.0.0. O core CLI agora é
> **100% determinístico**. Todas as funções dependentes de LLM foram movidas
> para a **Agent Layer** externa (Claude Code, Cursor, Copilot, Windsurf via
> `/maes-analyze`, `/maes-context-update`, etc.).

### Segurança e confiabilidade (hardening)

- **Proveniência blindada**: bullets de placeholder não-resolvidos (`[INFERRED]`, `[ASSUMED]`, `TODO:`/`FIXME:`, "confirme ou remova", "review required") são descartados na compilação — nunca mais viram assertion `explicit`. O matcher é preciso (case-sensitive em TODO/FIXME) para não apagar conteúdo legítimo em pt-BR ("Todo usuário…", "validar…"). `anti-hallucination.json` fica limpo (sem placeholders nem hipóteses promovidas a regra).
- **Trust signaling no grafo de arquitetura**: `architecture_map.json` e `impact-graph.json` ganham um bloco `reliability` (`authoritative:false`, `trust_level:"experimental"`, `agent_safe:false`) + detector de hub artificial; a tool MCP `maes_who_depends_on` avisa que as arestas são heurísticas.
- **MCP — todos os clientes em um comando**: `maes serve --write-mcp-config` (sem argumento) provisiona Claude Code (`.mcp.json` na raiz), VS Code/Copilot, Cursor, Continue e Windsurf. Configs de projeto são **portáveis** (`command: maes` + `args: ["serve"]`, sem caminhos absolutos → versionáveis); os globais fixam `--project-dir`. Claude Code é pré-aprovado em `.claude/settings.local.json` (incluído no `.gitignore`).

### Documentação

- **Roadmap reescrito** para o estado pós-hardening (V1.2 confiabilidade → V1.3 observabilidade → V1.4 adoção; Graph Accuracy como risco técnico nº 1).
- **Docs de MCP alinhadas** com `.mcp.json`, configs portáveis e o subcomando `maes serve`.

### Removido (BREAKING)

- **`maes quickstart`**: substituído pelo fluxo determinístico `maes init` + `maes sync`. O passo de análise por LLM agora é responsabilidade do agente externo `/maes-analyze`, instalado por `maes init`.
- **`maes context add` / `maes context apply-pr` / `maes context deduplicate`**: removidos. Geração e refinamento de contexto humano migram para o agente `/maes-context-update`.
- **`maes audit --ai`**: removido. O `maes audit` permanece como auditoria estática determinística; a análise por LLM agora roda fora do core.
- **Bundled templates `templates/ci/suggest-context-update.py`, `suggest-runtime-update.py` e workflows `maes-context-suggest.yml`, `maes-runtime-reminder.yml`**: removidos do template/scripts; equivalentes residem na Agent Layer.
- **Módulo `git_analysis.py`** e constantes/helpers internos (`_HELP_MODEL`, `_AI_SYSTEM_PROMPT`, `_AI_USER_PROMPT_TEMPLATE`, fonte `"ai"` em findings): limpeza de código morto.

### Adicionado

- **Landing page (`web/src/app/page.tsx`)**: nova seção _"O custo invisível da IA"_ — educativa sobre economia de tokens via Context Engineering (hierarquia de consumo, padrões anti-pattern e posicionamento MAES).
- **Doc `concepts/token-economics.mdx`**: aprofundamento técnico da seção da landing page.

### Mudado

- **`install.ps1` / `install.sh`**: pós-instalação executa `maes init` + `maes sync` (antes: `maes quickstart`). Mensagem de "API key obrigatória" agora se aplica somente a `maes eval`.
- **`maes doctor`**: mensagens de recuperação apontam para `maes sync` em vez de `maes quickstart`.
- **`maes audit`**: docstring/help do `_check_coverage_truncation` agora refere `/maes-analyze` agent.
- **Arquitetura**: Core CLI deterministico (`init`, `sync`, `validate`, `audit`, `doctor`, `eval`) ↔ Agent Layer LLM externa. `maes eval` permanece como único comando do core que chama LLM (usa `MAES_AGENT_MODEL`).

### Migração

| Comando antigo (≤ v0.16)         | Substituto v1.0.0                                                      |
| -------------------------------- | ---------------------------------------------------------------------- |
| `maes quickstart`                | `maes init` → `maes sync` (+ agente `/maes-analyze` no seu cliente IA) |
| `maes context add --from <file>` | Agente `/maes-context-update`                                          |
| `maes context apply-pr`          | Agente `/maes-context-update`                                          |
| `maes context deduplicate`       | Agente `/maes-context-update`                                          |
| `maes audit --ai`                | `maes audit` (estático) + revisão via agente                           |

---

## v0.14.0 — 2026-05-30

### Correções

- **OpenAI gpt-5.5 compatível no contexto**: provider OpenAI atualizado para usar `max_completion_tokens` nas chamadas de chat completions, corrigindo erro `unsupported_parameter` ao executar `maes context add/apply-pr`
- **Defaults provider-aware no CLI**: removido fallback fixo para modelo Claude nos fluxos `quickstart`, `analyze` e `context`, passando a respeitar `--model`, `MAES_AGENT_MODEL` e, na ausência, o padrão de cada provider
- **Label de provider/modelo nas mensagens**: saída de `context add` agora exibe provider e modelo efetivos (em vez de mensagem fixa de Claude)

### Manutenção

- **Default OpenAI do MAES**: modelo padrão do provider OpenAI atualizado para `gpt-5.5` no runtime e no template CI gerado
- **Web badge de versão**: hero da web atualizado para exibir a versão CLI `v0.14.0`

## v0.10.0 — 2026-05-27

### Novas funcionalidades

- **Context review status no fluxo local (revertido na sequência)**: introduzido suporte inicial para marcar contexto aplicado após `maes context apply-pr` (commit `d6e5fc6`), posteriormente revertido para centralizar a responsabilidade no CI

### Correções

- **CI de contexto**: `suggest-context-update.py` passa a marcar a seção `context` do comentário MAES como aplicada quando não houver novas sugestões para o PR

### Manutenção

- **Ajuste de arquitetura operacional**: revertida a lógica local de atualização de comentário para manter reconciliação exclusivamente no workflow de CI (`maes-context-suggest`)
- **Web badge de versão**: hero da web atualizado para exibir a versão CLI `v0.10.0`

## v0.9.0 — 2026-05-27

### Novas funcionalidades

- **Continue adapter support**: adicionado suporte completo ao adapter do Continue no pipeline de geração de adapters, com documentação atualizada para integração

### Correções

- **Code Reviewer orquestrador**: delegação de especialistas tornou-se portável entre projetos com gatilhos por sinais no diff em vez de paths fixos
- **Metrics Architect**: removido workflow dedicado para manter comportamento de instruction-only no Copilot

### Manutenção

- **Web badge de versão**: hero da web atualizado para exibir a versão CLI `v0.9.0`

## v0.8.0 — 2026-05-27

### Novas funcionalidades

- **`maes analyze` — coleta stack-agnostic por round-robin**: substituída a coleta baseada em `_SOURCE_PATTERNS` (com caps por tipo de arquivo) por um walker genérico que itera todos os arquivos fonte por extensão em round-robin entre diretórios, garantindo cobertura de todos os módulos do projeto independente de arquitetura
- **`analyze-instructions.md` — seção IMPLEMENTATION INTELLIGENCE**: nova seção no prompt do analyze instrui o LLM a detectar contratos de camada pelos imports reais (não por nomes de pasta), documentar fluxos completos de feature e identificar dependências proibidas que a IA violaria — stack-agnostic para qualquer arquitetura
- **Budget de coleta expandido para 200k chars**: aumentado de 100k para 200k, aproveitando a janela de contexto do Claude Sonnet

### Correções

- **Removido padrão Maxxi-específico** `src/forge/**/*.ts` de `_SOURCE_PATTERNS` — era acoplado a um projeto interno
- **`_MIGRATION_GLOB` expandido para 9 ORMs**: era Prisma-only, agora cobre Rails, Alembic, Laravel, Flyway, Liquibase e outros
- **`_DEP_FILES` em `staleness.py`**: adicionados Ruby (Gemfile/lock), PHP (composer.json/lock), pnpm-lock.yaml, Pipfile/lock, build.gradle.kts

---

## v0.7.1 — 2026-05-26

### Documentação

- Adicionada comparação "MAES vs Edição Manual" no guia de adoção — explica por que não editar adapters manualmente e quando cada abordagem faz sentido

---

## v0.7.0 — 2026-05-26

### Novas funcionalidades

- **Campo `workflow` em agent YAML** — agents podem definir workflows faseados com `argument_hint` (ex: `"start | finish"`) e conteúdo markdown estruturado por fase
- **Geração de SKILL.md para GitHub Copilot** — quando um agent define `workflow`, o `maes sync` gera automaticamente `.github/skills/{id}/SKILL.md` invocável com `@{agent} {argumento}` no Copilot Chat
- **Slash commands enriquecidos no Claude Code** — `.claude/commands/{id}.md` agora inclui `args: {argument_hint}` na description e o workflow appendado ao final
- **Agent `release` repo-específico** — skin de Release Manager com workflow `changelog | release` para fechar versões: gera changelog, bumpa versão, commit, tag e reinstala

### Documentação

- Integração Copilot atualizada com nova seção "Skills com workflow — .github/skills/"
- Visão geral de integrações atualizada: diagrama mermaid e tabela de adapters incluem SKILL.md
- Guia "Usando os Agents" atualizado: git-guide documentado com argumentos `start`/`finish`, comparativo de ferramentas ampliado com linha "Skills com workflow"

### Manutenção

- `git-guide.agent.yaml` (repo e catálogo) atualizado com campo `workflow` completo (fases start/finish)
- `adapters.py`: função `_render_copilot_skill()` adicionada; `_render_claude_command()` atualizado para suportar `workflow`; `generate_copilot_adapter()` gera SKILL.md quando workflow presente

---

## v0.6.0 — 2026-05-20

### Novas funcionalidades

- Gateway LiteLLM centralizado via `MAES_BASE_URL` + `MAES_API_KEY` (virtual key)
- Suporte multi-provider simultâneo: Anthropic, GitHub Models e Gemini com `MAES_PROVIDER` para forçar provider específico

### Manutenção

- Workflows CI atualizados com `GEMINI_API_KEY` e `MAES_PROVIDER`
- Hero badge e docs bump para v0.6.0

---

## v0.5.1 — 2026-05-15

### Correções

- CI: instalação do maes via GitHub source tag em vez de PyPI
- Vendor: cópia apenas dos módulos necessários para CI (excluindo LLM, setup e runtime)
- Upgrade: atualização de GitHub Actions workflows mesmo quando versão já bate

### Manutenção

- SonarLint S3776: extração de `_upgrade_no_migrations` e `_finalize_upgrade` para reduzir complexidade cognitiva
- SonarLint S5781: remoção de duplicata em frozenset

---

## v0.5.0 — 2026-05-10

### Novas funcionalidades

- Deduplicação semântica de assertions com comando `maes deduplicate`
- Output em PT-BR para comandos de contexto

### Correções

- Context add: resolução de issues SonarLint em `context_add_cmd`

---

## v0.4.0 — 2026-05-01

### Novas funcionalidades

- `maes context apply-pr`: aplica sugestões do CI workflow como operação atômica com deduplicação automática
- `maes audit --ai`: ponto de entrada LLM no fluxo de auditoria

---

## v0.3.0 — 2026-04-20

### Novas funcionalidades

- MCP Server (`maes serve`) com três ferramentas: `maes_get_agent_context`, `maes_check_guard`, `maes_list_agents`
- Suporte a Cursor via `.cursor/mcp.json`

---

## v0.2.0 — 2026-04-10

### Novas funcionalidades

- Pipeline de compilação de 7 estágios: INGEST → NORMALIZE → DEDUPLICATE → LAYER → CONFLICT → COMPILE → ADAPTERS
- Sistema de context tiers: Hot (≤800 tokens, sempre), Warm (≤4000 tokens, por relevância), Cold (nunca auto-carregado)

---

## v0.1.0 — 2026-04-01

### Novas funcionalidades

- Versão inicial do MAES CLI
- `maes init`, `maes sync`, `maes validate`, `maes analyze`
- Adapters para Claude Code, Cursor, Windsurf e GitHub Copilot
- Sistema de 7 layers de prioridade com TTL e staleness detection
