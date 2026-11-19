# Findings — enforcement de guards ausente + imprecisão do dep-graph

> Nota de registro (não é decisão nem RFC ratificada). Origem: teste do MCP `maes-ldc`
> gerado ao rodar o MAES em `C:\Projects\ldc`. Duas observações surgiram durante o teste;
> a investigação abaixo confirmou que **ambas têm causa-raiz no framework** (este repo),
> não na configuração do projeto alvo. A implementação será feita depois, em modo plano.

## Contexto

Ao testar as 4 tools do MCP no LDC, o Claude reportou que estavam operacionais, com duas
observações de conteúdo/config:

1. `maes_check_guard` devolveu **ALLOWED** para "alterar `user_points` direto via
   `prisma.update` para corrigir saldo" — ou seja, a regra append-only ("pontos são dinheiro")
   existe como assertion mas **não bloqueia** aquele path.
2. `maes_who_depends_on` só indexa em **granularidade de diretório**; consulta por arquivo
   (`ledger.service.ts`) cai em `NOT_INDEXED`. As edges são declaradas
   `EXPERIMENTAL/heuristic` (não confiáveis sem verificar a fonte).

---

## Observação #1 — regra crítica não vira guard bloqueante (silencioso)

### Causa-raiz (confirmada)

Guards **não são autorados** pelo usuário — são projeções automáticas de assertions,
regeneradas a cada `maes sync`.

- `derive_guards()` → `_build_guard_entry()` em
  [compiler.py:972-1011](../../template/scripts/tools/maes/compiler.py).
- Gate `_should_emit_guard(a)` ([compiler.py:968-969](../../template/scripts/tools/maes/compiler.py)):
  `a.type in (CONSTRAINT|COMPLIANCE|CONTRACT) AND (bool(a.paths) OR a.layer <= 3)`.
- Política ([compiler.py:960-984](../../template/scripts/tools/maes/compiler.py)):
  `policy="block"` só quando `layer <= 2` **E** a assertion tem `paths`; sem paths, degrada
  para `policy="inform"`, `paths=["**"]`, `guard_type="contextual"`.
- `a.paths` vem de `_extract_paths()` ([compiler.py:69-92](../../template/scripts/tools/maes/compiler.py)),
  cujo regex **só captura tokens contendo `/` ou `*`**.

Consequência: uma regra de negócio como "`user_points` é append-only" nomeia uma
**entidade/tabela**, não um path; cai em **layer 5 (domain)** e não tem `/` nem `*` no texto
→ `_should_emit_guard` retorna **False** → **nenhum guard é gerado** (nem contextual).
Por isso `maes_check_guard` (que lê **somente** `synthesis/guards.json`, nunca assertions —
[mcp_server.py:328-343](../../template/scripts/tools/maes/mcp_server.py)) respondeu ALLOWED.

### O problema estrutural

Não há **nenhuma** rede de segurança que avise: `maes audit` tem categoria `guards`
([audit_cmd.py](../../template/scripts/tools/maes/audit_cmd.py)) mas **nenhum check de
cobertura assertion↔guard**. Os drops de `_should_emit_guard`/`_dedup_guards_by_paths`
são silenciosos. Ou seja: uma regra crítica ("pontos são dinheiro") pode ficar sem
enforcement e ninguém percebe.

### Plano proposto (obs #1)

- **A1 (prevenção upstream)** — instruir o analyzer em
  [analyze-instructions.md](../../template/scripts/tools/maes/templates/analyze-instructions.md)
  a, para toda constraint financeira/irreversível/append-only/segurança: (a) formular como
  CONSTRAINT proibitivo e (b) **sempre** incluir o path glob concreto (`src/points/**`) no
  texto, para que um guard escopado seja derivado.
- **A2 (rede de segurança)** — novo check `_check_guard_coverage` em `audit_cmd.py`:
  assertion proibitiva/crítica (polaridade "forbid", ou keywords dinheiro/irreversível/
  append-only, ou layer ≤ 2) que **não** produziu guard bloqueante escopado → WARNING/CRITICAL
  explícito ("regra X não está sendo enforçada; adicione um path glob"). Deixar de silenciar
  os drops.
- **A3 (opcional, follow-up)** — inferência entidade→path: mapear nomes de entidade/tabela
  citados no claim (`user_points`) para o path do módulo via architecture map, atribuindo
  `paths` automaticamente. Fecha o gap sozinho, mas com risco de escopo fabricado.

---

## Observação #2 — dep-graph TS impreciso (edges perdidas e fabricadas)

### Causa-raiz (confirmada)

- `_extract_ts_imports()` descarta tudo que **não é import relativo** (`spec.startswith(".")`)
  — [dep_analysis.py:245-259](../../template/scripts/tools/maes/dep_analysis.py). Aliases do
  `tsconfig` (`@/points/...`) e imports absolutos somem.
- O `tsconfig.json` **já é coletado** na discovery
  ([stage_1_discovery.py:70](../../template/scripts/tools/maes/pipeline/stage_1_discovery.py))
  e chega a `build_dependency_edges` via `all_files` — ou seja, a resolução de alias é
  viável sem coleta extra.
- `_add_import_edges()` casa por **substring** (`imp_norm in prefix`)
  — [arch_analysis.py:557-569](../../template/scripts/tools/maes/arch_analysis.py) — o que
  **fabrica** edges. Origem do aviso EXPERIMENTAL em
  [mcp_server.py:521-523](../../template/scripts/tools/maes/mcp_server.py).
- Nós do architecture map são de **nível de módulo/diretório** (por design — `collapse_candidates`),
  por isso consultas por arquivo caem em `NOT_INDEXED`.

### Plano proposto (obs #2)

- **B1** — resolver path-aliases do `tsconfig` (`baseUrl` + `compilerOptions.paths`) em
  `build_dependency_edges`, capturando imports `@/...` que hoje somem.
- **B2** — trocar o match por substring de `_add_import_edges` por match com fronteira de
  path, eliminando edges fabricadas.
- **B3** — no MCP, fazer `who_depends_on` resolver um arquivo para o **nó de diretório que o
  contém** (longest-prefix) em vez de `NOT_INDEXED`, mantendo honesto que a granularidade é
  de módulo. Atualizar o texto do aviso EXPERIMENTAL conforme o que passar a ser confiável.

---

## Observação #3 — `_extract_paths` extrai `/` espúrio (mini-bug)

### Causa-raiz (confirmada em campo)

`_extract_paths()` ([compiler.py:83-92](../../template/scripts/tools/maes/compiler.py)) roda o
regex `_PATH_RE` ([compiler.py:69-75](../../template/scripts/tools/maes/compiler.py)), cuja 1ª
alternativa `` `([^`]*/[^`]*)` `` casa qualquer conteúdo entre backticks contendo `/`. Um
trecho como `` `a`/`b` `` (dois termos em backticks separados por uma barra literal) faz o
motor casar através do `` `/` `` do meio e extrair o token **`/`** como se fosse um path.

Efeito: um guard derivado ganha `"/"` na lista de `paths` (visto na prática no LDC:
`paths=["/", "src/points/ledger/**", "src/points/**"]`). Um path de guard `"/"` é ruído e
pode super-casar no glob do `check_guard`.

### Contorno aplicado (manual)

Reescrever `` `update`/`delete` `` como `` `update` ou `delete` `` no texto do claim elimina o
token. Mas é frágil — depende de o autor da regra saber disso.

### Plano proposto (obs #3)

- **C1** — descartar em `_extract_paths` tokens degenerados: path sem nenhum caractere de
  nome (só `/`, ou `/`+`*`), e normalizar. Baixo risco, corrige na raiz.

---

## Observação #4 — matcher de guard não é agnóstico a prefixo de monorepo

### Causa-raiz (confirmada em campo)

`_match_guard_path()` ([mcp_server.py:110-127](../../template/scripts/tools/maes/mcp_server.py))
converte um glob como `src/points/**` no regex `src/points/.*` e usa `re.fullmatch` —
**ancorado no início do path**. Em workspace multirepo, o `.maes/` fica na raiz do workspace e
os paths canônicos carregam o prefixo do sub-repo
(`ldc-gamif-web-backend-nodejs-louisgames/src/points/...`). Resultado: um guard escrito como
`src/points/**` **não casa** o path prefixado → **ALLOWED** (fura o guard). Só existe um
tratamento especial para patterns que já começam com `**/` (fallback recursivo em
[mcp_server.py:125-126](../../template/scripts/tools/maes/mcp_server.py)).

Prova (rodando a própria `_match_guard_path`):

| pattern           | `src/points/x.ts` | `<repo>/src/points/x.ts` | `<repo>/src/auth/x.ts` |
| ----------------- | ----------------- | ------------------------ | ---------------------- |
| `src/points/**`   | BLOCK             | **allow (fura!)**        | allow                  |
| `**/src/points/**`| BLOCK             | BLOCK                    | allow (sem over-block) |

### Band-aid aplicado (LDC)

Reescrevi os globs da regra para `**/src/points/**` (e `**/src/points/ledger/**`) — casa os dois
formatos, sem over-block. **Mas é frágil**: obriga todo autor de regra em workspace multirepo a
lembrar do prefixo `**/`; single-repo escreve `src/points/**`, multirepo escreve
`**/src/points/**`. O autor não deveria precisar conhecer o layout do workspace — mesma classe de
fragilidade da obs #1.

### Plano proposto (obs #4)

- **D1** — tornar o matcher **agnóstico a prefixo de monorepo**: um glob repo-relativo
  (`src/points/**`) deve casar em qualquer ponto da árvore por padrão (semântica implícita de
  `**/`), preservando ancoragem só quando o autor explicitamente prefixar com `/` ou `./`.
  Assim MAES "simplesmente funciona" em single-repo **e** multirepo sem o autor saber do layout.
  Considerar também normalizar paths na compilação/emissão para uma forma canônica única.

---

## Validação em campo (LDC, projeto alvo)

A obs #1 foi validada end-to-end no LDC, confirmando o modelo mental:

1. A regra append-only em `.maes/context/human/compliance.md` **não** produzia guard porque o
   bullet continha os marcadores de staging `[INFERRED]` + "confirme ou remova após revisão"
   — descartados por `_has_unresolved_marker` ([compiler.py:200-225](../../template/scripts/tools/maes/compiler.py)).
2. Removidos os marcadores (regra verificada contra o trigger `trg_user_points_append_only` e
   os testes `ledger.invariants.spec.ts` do backend) **e** com o path glob no texto, o
   `maes sync` passou a derivar **automaticamente** um guard
   `policy=block, guard_type=enforcement, layer=1, paths=["src/points/ledger/**","src/points/**"]`.
3. **Confirmado que não existe superfície de autoria de guard**: o guard nasce só de
   `derive_guards(assertions)`. Bastam três condições no lado da assertion — tipo
   CONSTRAINT/COMPLIANCE/CONTRACT, `layer ≤ 2` (aqui via frontmatter `layer: 1` do
   `compliance.md`) e path extraível. Isso reforça o valor de **A2** (a degradação silenciosa
   para `inform` quando falta path é justamente o modo de falha real).

---

## Escopo sugerido para o primeiro corte

**A1 + A2 + B1 + B2 + B3 + C1 + D1** (alto valor, baixo risco). **A3** como follow-up.

> **D1 é prioritário para o requisito "MAES tem que funcionar em multirepo e single-repo":**
> enquanto não existir, todo guard escopado num workspace multirepo depende do band-aid `**/`.

## Próximo passo

Retomar em **modo plano** para detalhar a implementação e os testes de cada item.
