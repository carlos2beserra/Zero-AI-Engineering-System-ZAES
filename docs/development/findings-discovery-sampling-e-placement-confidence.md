# Findings — sub-amostragem do Stage 1 + confiança indevida no Observed Placement

> Nota de registro (não é decisão nem RFC ratificada). Origem: rodar `maes build-arch-map` duas
> vezes no mesmo projeto (`C:\Projects\ldc`, workspace multirepo). A segunda rodada produziu um mapa
> **menor** — 49 → 22 nós — depois de o time adicionar código e documentação. A investigação
> confirmou que **todas as causas-raiz estão no framework** (este repo), não na configuração do
> projeto alvo. Continua a numeração do findings anterior
> ([findings-guard-enforcement-e-depgraph-precisao.md](findings-guard-enforcement-e-depgraph-precisao.md),
> obs #1–#4). Decisão de política formalizada em [ADR 0009](../adr/0009-observacao-exige-populacao-conhecida.md).

## Contexto

O sintoma relatado foi contra-intuitivo: **quanto mais o time documentava, menos código o mapa
enxergava**. A hipótese inicial — saturação do orçamento de 200k chars pelos 116 arquivos `.md`
(1 MB) em `docs/` — se mostrou apenas parcialmente correta, e não é a causa principal. Os docs são
limitados a 100k chars / 50 arquivos pelo `_DocCollector`
([stage_1_discovery.py:233-247](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py)),
teto que já estava saturado antes da segunda rodada.

Investigando o código, apareceram seis causas independentes.

---

## Observação #5 — `.tsx`, `.jsx`, `.vue` e `.svelte` são invisíveis ao Stage 1

### Causa-raiz (confirmada)

`_SOURCE_EXTENSIONS` ([stage_1_discovery.py:20](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py))
não inclui essas extensões, e as strings `tsx`/`jsx`/`vue` **não aparecem em nenhum lugar** do
pacote `pipeline/`. Como `_build_source_dir_map` e `_is_entity_file` filtram por esse set, um
projeto React/Next não tem **nenhum** arquivo elegível fora de `_PRIORITY_FILES`.

O Stage 2 sabe lidar com eles: `arch_analysis._SOURCE_EXTS`
([arch_analysis.py:71-74](../../template/scripts/tools/maes/arch_analysis.py)) inclui `.tsx`/`.jsx`.
**Os dois sets divergiram** — o Stage 1 nunca entrega o que o Stage 2 sabe processar.

### O problema estrutural

"Zero nós do frontend" foi atribuído a orçamento esgotado. Não é: é um filtro que nunca deixa o
frontend entrar. Duas definições de "arquivo de fonte" divergindo silenciosamente é o modo de falha,
e nada no sistema detecta a divergência.

### Plano proposto (obs #5)

- **E1** — um único conjunto canônico `CANONICAL_SOURCE_EXTENSIONS` em `models.py` (módulo base sem
  imports internos), consumido por Stage 1 e `arch_analysis`. Subconjuntos por **capacidade**
  (`IMPORT_PARSEABLE_EXTENSIONS`) derivam dele e são nomeados pela capacidade, nunca literais soltos.

---

## Observação #6 — `_PRIORITY_FILES` só é resolvido na raiz do projeto

### Causa-raiz (confirmada)

`_collect_priority` resolve cada entrada como `project_dir / name`
([stage_1_discovery.py:347-354](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py)).
Em workspace multirepo — o caso do LDC — **nenhum `package.json` é encontrado**, e
`_detect_frontend_framework` devolve `None` → `is_frontend_project: false` por ausência de evidência,
não por observação. Agrava: `_detect_frontend_framework` casa por caminho exato
(`norm == "package.json"`), então mesmo se coletado, `apps/web/package.json` não seria reconhecido.

### O problema estrutural

Mesma classe da obs #4/D1 do findings anterior: **o MAES tem de funcionar em single-repo e multirepo
sem o autor conhecer o layout**. Aqui o efeito é um fato arquitetural (existe frontend?) respondido
errado com aparência de certeza.

### Plano proposto (obs #6)

- **E2** — `_find_project_roots`: raiz + subdiretórios (profundidade ≤ 2) com manifesto, ordenados
  por **prioridade de tipo de manifesto** e só depois lexicograficamente, limitados por
  `_MAX_PROJECT_ROOTS`. Casamento por basename em `_detect_frontend_framework`. Configs de framework
  (`next.config.*`, `vite.config.*`, …) entram em `_PRIORITY_FILES` — hoje `_CONFIG_FILE_TO_FRAMEWORK`
  é inalcançável porque só `angular.json` está na lista.
- **E3** — truncamento de raízes **observável**: `project_roots_discovered/analyzed/truncated`. Um
  limite de proteção não pode parecer ausência de evidência. Regra de leitura:
  `is_frontend_project: false` + `project_roots_truncated: true` **não é evidência negativa**.

---

## Observação #7 — a cobertura é auto-referente

### Causa-raiz (confirmada)

`files_total = len(all_file_paths)`, derivado de `discovery.files`
([stage_2_arch_builder.py:85-87](../../template/scripts/tools/maes/pipeline/stage_2_arch_builder.py))
— a própria amostra truncada em 200k chars. O artefato reportou **60,5%** de cobertura (26/43
coletados) enquanto o projeto tem 848 arquivos de fonte: cobertura efetiva de ~5%.

`is_frontend_project` ([:53](../../template/scripts/tools/maes/pipeline/stage_2_arch_builder.py)) e
as arestas (`build_dependency_edges(nodes, all_files)`, [:65](../../template/scripts/tools/maes/pipeline/stage_2_arch_builder.py))
também são decididos sobre a amostra. O Stage 3 varre o projeto inteiro, mas seu resultado só
alimenta o `boundary_map` — a informação completa de dependência existe e é descartada.

### O problema estrutural

Uma métrica de cobertura cujo denominador é a própria amostra é **estruturalmente incapaz** de
revelar sub-amostragem. Não é observação: é tautologia. E 60,5% lê como aceitável.

### Plano proposto (obs #7)

- **E4** — separar **população** (todos os arquivos de fonte, computação pura sobre caminhos) de
  **amostra de conteúdo** (limitada por orçamento). `modeled_coverage_pct` mede modelagem contra a
  população; `sampling_ratio` mede leitura contra a mesma população. Ambos emitidos, schema 2.1.
- **E5** — topologia construída a partir do inventário de caminhos: `build_candidates` já ignora o
  conteúdo, então a estrutura completa sai de graça. Conteúdo passa a ser apenas enriquecimento
  (`semantic_weight`, `entry_points`), com `files_sampled` por nó registrando a evidência disponível.

---

## Observação #8 — a reserva de 40% do orçamento para código não é garantida

### Causa-raiz (confirmada)

`_collect_ci_workflows`, `_collect_auth_models` e `_collect_domain_models` são **explicitamente
isentos** do `_PRIORITY_BUDGET_RATIO`
([stage_1_discovery.py:344](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py)) e param
apenas em `at_limit()` (200k). `_collect_domain_models` coleta até 40 arquivos com cap de 10–12k cada
— até ~480k, o **dobro** do orçamento total. Sozinho pode zerar o BFS de código-fonte.

O critério de `_is_entity_file` é largo: qualquer arquivo de fonte cujo *stem* contenha `model`,
`entity`, `schema` ou `domain` ([:305-313](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py)).
Num NestJS isso pega muita coisa. **Esta é a explicação mais provável do 49 → 22**, não os docs: se
entraram entidades/schemas novos entre as rodadas, o BFS perdeu o que sobrava.

### O problema estrutural

O split 60/40 existe no código como comentário e intenção, não como invariante verificável.

### Plano proposto (obs #8)

- **E6** — soft cap no `_Collector`: `add()` e `at_limit()` respeitam um limite temporário que
  `_collect_priority` define para toda a fase. Todos os sub-coletores param sozinhos, sem editar
  nenhum deles. A ordem das fases já é a desejada (nomeados → CI → auth → domain → docs): docs ficam
  por último e são os primeiros espremidos.
- **E7** — `build-arch-map` passa `skip_existing_docs=True`. Docs não contribuem nada para topologia
  (`build_candidates` filtra por extensão de fonte). O parâmetro existe desde sempre e hoje é
  passado como `True` em **zero** lugares fora dos testes.

---

## Observação #9 — o Observed Placement vaza conclusão sem lastro para o CLAUDE.md

### Causa-raiz (confirmada em campo)

`_dominant_prefix` ([compiler.py:1139-1169](../../template/scripts/tools/maes/compiler.py)) soma o
`file_count` de cada nó também no prefixo de **1 segmento**. Quando todos os nós compartilham a raiz,
o resultado é `coverage = 100%` → tier `high` → renderizado **sem** o `⚠️` por
`_render_placement_section` ([adapters.py:124-147](../../template/scripts/tools/maes/adapters.py)).

No LDC saiu `Service → ldc-gamif-web-backend-nodejs-louisgames (100%)`: **o prefixo menos informativo
possível com a confiança máxima**, orientando onde colocar código novo. O caminho do vazamento é
`architecture_map.json` → [`_build_placement_map`](../../template/scripts/tools/maes/compiler.py) →
`placement-map.json` → `_render_placement_section` → CLAUDE.md.

### O problema estrutural

O Analyze afirmou uma convenção que a evidência (~5% de amostra) não sustenta, e o pior caso de
prefixo é justamente o que recebe a maior confiança.

### Plano proposto (obs #9)

- **E8** — **refusal-to-emit**: abaixo do piso de amostragem, `status: insufficient_sample` e nenhuma
  placement. Fail-closed — ausência de `sampling_ratio` conta como insuficiência, o que faz o `sync`
  disparado pelo próprio `maes upgrade` omitir a seção em vez de reemitir a errada.
- **E9** — descarte **estrutural** do prefixo que não discrimina: se o prefixo dominante é o
  ancestral comum de todos os nós do mapa, não responde "onde vive um Service?". Comparar com
  `project_dir.name` seria ambíguo (diretório interno homônimo) e nome de checkout não é informação
  arquitetural.
- **E10** — prefixo de 1 segmento nunca recebe `high`.
- **E11** — status próprio `no_observed_convention` para amostra suficiente + mapa válido + nenhum
  prefixo discriminante. **Ausência de convenção observável ≠ falta de dados.**
- **E12** — política de suficiência em módulo próprio (`sampling_policy`), separada do mecanismo de
  emissão: impact graph, entry points e dependency confidence farão a mesma pergunta.

---

## Observação #10 — múltiplas enumerações independentes da mesma população

### Causa-raiz (confirmada)

Só dentro do Stage 1 há **dois** `rglob("*")` completos —
[:326](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py) em `_collect_domain_models` e
[:392](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py) em `_build_source_dir_map` —
mais **36 globs recursivos** em `_collect_auth_models`
([:278-284](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py)), um por padrão de
`_AUTH_FALLBACK_GLOBS`.

Esse último é também **bug de correção**: diferente de `_collect_domain_models`, ele **não** chama
`_in_ignored`, então `.venv/**/models/user.py` ou `node_modules/**/model.ts` podem ser coletados como
modelo de domínio do projeto.

### O problema estrutural

Dois pontos do código podem discordar sobre "quais arquivos existem", e a correção da obs #7 exigiria
uma terceira varredura se o inventário nascesse solto.

### Plano proposto (obs #10)

- **E13** — `scan_project()` como **fonte única de verdade para enumeração estrutural**, consumida
  por `_build_source_dir_map`, `_collect_domain_models` e `_collect_auth_models`. Contrato:
  rel-posix normalizado, ordem determinística, sem duplicatas, símlinks fora, nenhuma classificação
  arquitetural, estabilidade sobre caminho e existência apenas (metadado nunca influencia).
- Percursos que **permanecem** por serem trabalho diferente: `analyze_imports` (lê conteúdo; passa a
  consumir o inventário quando as arestas migrarem, junto de B1/B2) e `build_file_tree` (projeção
  distinta — inclui diretórios e não-fontes, corta em profundidade 4 e 30 entradas por nível).

---

## Escopo sugerido para o primeiro corte

**E1 + E2 + E3 + E4 + E5 + E6 + E7 + E8 + E9 + E10 + E11 + E12 + E13.**

Fora do primeiro corte, por dependerem de trabalho já registrado:

- **Arestas do projeto inteiro** — mover `build_dependency_edges` para consumir o scan completo do
  Stage 3 e remover o hack de `NamedTemporaryFile` em `_extract_file_imports`
  ([arch_analysis.py:538-554](../../template/scripts/tools/maes/arch_analysis.py), que escreve um
  arquivo temporário **por arquivo analisado**). **Sobrepõe-se aos itens B1/B2** do findings anterior
  e deve ser tratado uma única vez com eles. Nessa ocasião, `analyze_imports` passa a consumir o
  inventário do E13.

---

## Follow-ups rastreáveis (dívida criada por este corte)

| # | Item | Condição de remoção / execução |
|---|---|---|
| F1 | Fallback `discovery.source_paths or [fp for fp, _ in discovery.files]` no Stage 2 | Quando todos os produtores emitirem `source_paths`: tornar o campo obrigatório (sem default) e apagar o `or`. Emite aviso explícito enquanto existir. |
| F2 | Adaptador `build_candidates(files)` | Quando os consumidores forem migrados para `build_candidates_from_paths`. Implementação canônica é a de paths; o adaptador nunca ganha lógica. |
| F3 | Otimização de fan-in em `_compute_semantic_weights` (`all_content.count(leaf)` por candidato, O(candidatos × amostra)) | **Medido — não executar.** Ver abaixo. |
| F4 | Enum para o estado da detecção de frontend | Se a regra de leitura de `project_roots_truncated` provar insuficiente em campo. |
| F5 | Representação lazy/streaming do inventário | Se projetos muito grandes exigirem. Compatível com o contrato do `scan_project`; não requer nova ADR. |

### F3 — medição que dispensa a otimização

Projeto sintético de **960 arquivos** de fonte (~8k cada, 120 diretórios), rodando
`build-arch-map` completo:

| Etapa | Tempo | Observação |
|---|---|---|
| Stage 1 (discovery + inventário) | 1,55 s | uma única enumeração |
| Stage 3 (`analyze_imports`) | **31,1 s** | lê **todo** arquivo de fonte |
| Stage 2 (arch builder) | **0,16 s** | onde a mudança deste corte atua |
| └ `_compute_semantic_weights` | **0,027 s** | o alvo do F3 |

Conclusão: o custo temido no F3 é **0,08% do total** e não justifica mudança — a preocupação
com O(candidatos × amostra) não se materializa porque o numerador cresce mas a amostra
permanece limitada pelo orçamento. **F3 fica registrado como não-executar**, com a medição como
justificativa.

O que a medição revelou de fato: **97% do tempo é I/O do Stage 3** — `cProfile` atribui 32,3 s
dos 33 s a `_io.open`, ~34 ms por arquivo (custo do SO/antivírus nesta máquina, não do código).
É pré-existente e não foi alterado por este corte, mas é **dado relevante para B1/B2**: quando
as arestas migrarem para o Stage 3, ele passará a consumir o inventário e vale medir de novo com
a leitura sendo o gargalo conhecido.

---

## Finding registrado — CLI anterior lendo schema futuro

> **Finding.** Um CLI anterior ao schema atual pode degradar **silenciosamente** ao consumir
> artefatos do Analyze: lê 2.1 com `.get`, não encontra os campos novos e segue como se estivesse
> tudo bem.
> **Status.** Conhecido; **não corrigível retroativamente** nas versões já publicadas — um `maes`
> 1.3.0 já instalado não sabe que 2.1 existe.
> **Mitigação.** Schema compatibility guard a partir de 2.1: `schema_version` maior que o suportado
> é rejeitado explicitamente (`unsupported_schema`), distinto de `insufficient_sample` (válido mas
> anterior) e de `invalid_artifact` (estrutura quebrada). Versão desconhecida nunca degrada calado.

---

## Próximo passo

Implementação conforme o plano aprovado, em 3 PRs (bugs → estrutura → testes) mais a validação do
fluxo oficial de atualização (`maes upgrade` → `maes build-arch-map` → `maes sync`).
