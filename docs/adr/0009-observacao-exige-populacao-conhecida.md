# ADR 0009 — Observação exige população conhecida

Status: Aceito · Data: 2026-08-03 · Owner: team:architecture

> **Definição.** Uma afirmação observacional exige **população conhecida**. Métrica de cobertura cujo
> denominador é a própria amostra não é observação — é tautologia. População e leitura da população
> são fatos distintos e **nunca** se conflatam num único número.

## Contexto

O `build-arch-map` declara no seu próprio contrato receber "full project filesystem snapshot (no
partial views)", mas o Stage 1 entrega uma amostra limitada a 200k chars — um orçamento que existe
para caber em janela de LLM, embora `build-arch-map` seja zero-LLM. Sobre essa amostra o Stage 2
calculava cobertura usando **a própria amostra como denominador**, decidia `is_frontend_project` e
derivava o Observed Placement que é renderizado no `CLAUDE.md`.

Em campo (workspace multirepo com 848 arquivos de fonte) o artefato reportou 60,5% de cobertura sobre
43 arquivos coletados — ~5% efetivos — e emitiu `Service → <raiz do repositório> (100%)` com confiança
`high`, orientando onde colocar código novo. Investigação completa em
[findings-discovery-sampling-e-placement-confidence.md](../development/findings-discovery-sampling-e-placement-confidence.md).

## Definições

Declaradas uma vez, reutilizadas por todo o restante desta ADR:

- **População** — conjunto completo de entidades observáveis **segundo a definição canônica da
  plataforma**. Não é "todos os arquivos": é todos os arquivos que pertencem à definição oficial de
  código-fonte (`CANONICAL_SOURCE_EXTENSIONS`), excluídos os diretórios ignorados. A qualificação é o
  ponto — sem ela, "população" viraria elástica e cada consumidor teria a sua.
- **Amostra** — subconjunto da população efetivamente analisado (aqui: lido, dentro do orçamento de
  conteúdo).
- **Cobertura** — relação entre o **modelo produzido** e a população (`modeled_coverage_pct`).
- **Amostragem** — relação entre a **evidência coletada** e a população (`sampling_ratio`).

## Decisão

### Enumeração × amostragem

O Analyze distingue **enumeração** (a população inteira, computação pura sobre caminhos) de
**amostragem de conteúdo** (limitada por orçamento). São fatos de tipos diferentes — mesmo princípio
da [ADR 0005](0005-autoridade-normativa-observacional.md) — e ambos são emitidos: `modeled_coverage_pct`
mede *cobertura*, `sampling_ratio` mede *amostragem*, ambos contra a mesma população.

**Amostragem é medida em população, não em volume.** `sampling_ratio` é `files_sampled / files_total`;
cada arquivo pesa 1, independente do tamanho. **Mede** a quantidade de entidades da população sobre as
quais existe evidência. **Não mede** volume de código, linhas analisadas, cobertura semântica nem
profundidade da análise. Dois projetos de 100 arquivos, um com 20 linhas cada e outro com 3.000, têm o
mesmo `sampling_ratio` — isso é **intencional**, não imprecisão a corrigir. Substituir por
`chars_read / chars_total` destruiria a relação com a população e faria a métrica medir orçamento em
vez de evidência: explicitamente rejeitado.

### Refusal-to-emit

Uma afirmação só é emitida quando existe evidência **do tipo que ela exige**. São dois tipos, e
conflatá-los é o mesmo erro de categoria que esta ADR proíbe:

| Tipo de afirmação | Exemplo | Evidência | Política |
| --- | --- | --- | --- |
| Derivada de **conteúdo** | `entry_points`, `dep_edges` | `sampling_ratio` | `has_sufficient_sample()` |
| Derivada de **estrutura** | "onde vive um Service?" | topologia construída sobre a população | `has_population_semantics()` |

O Observed Placement é **estrutural**: sai de `path`, `type` e `file_count`, todos derivados da
população. Portanto a pré-condição não é "quanto conteúdo foi lido", e sim "a topologia deste
artefato foi construída sobre a população?" — respondida pelo `schema_version`. **Fail-closed:**
versão ausente, ilegível ou anterior a 2.1 é insuficiência, não permissão, o que é o que impede o
`sync` disparado pelo `maes upgrade` de reemitir uma conclusão derivada de amostra.

> **Correção pós-campo (2026-08-03).** A primeira implementação gateava o placement em
> `sampling_ratio ≥ 0.25`. Validando no repositório que originou esta ADR, o resultado foi um
> `insufficient_sample` que suprimiu **cinco observações válidas**: 941 arquivos de fonte com
> topologia completa, mas apenas 3,2% de conteúdo lido dentro do orçamento — condição normal e
> permanente em projetos grandes. O gate media a grandeza errada. Ressalva registrada: a
> *granularidade* dos nós ainda é parcialmente influenciada pela amostra, porque `semantic_weight`
> lê conteúdo e bloqueia collapse; os caminhos, porém, são todos reais.

Nenhum prefixo de 1 segmento recebe confiança `high`: quando todos os nós compartilham uma raiz, o
prefixo de profundidade 1 pontua 100% por construção.

Um prefixo que **não discrimina** carrega informação zero e é descartado. O teste é **estrutural** —
comparação de caminhos entre nós —, nunca por nome de diretório: um diretório interno homônimo daria
falso positivo, e o nome da pasta de checkout não é informação arquitetural.

A regra vale apenas quando o mapa tem **mais de uma categoria**, porque só aí há o que discriminar.
Num mapa de categoria única todo nó é um Service por definição, então o prefixo compartilhado **é** a
resposta — descartá-lo suprimiria a observação correta "os services vivem em `src/services`".

**Ausência de convenção observável ≠ falta de dados.** Mapa válido cujos nós não tenham prefixo
discriminante é uma observação legítima e informativa, reportada como `no_observed_convention`. Cada
estado responde uma pergunta diferente: `generated` (convenção observada), `no_observed_convention`
(observei, não há), `stale_schema` (topologia construída sobre amostra, não população),
`invalid_artifact` (estrutura quebrada), `unsupported_schema` (gerado por MAES mais novo — atualize
o CLI), `empty` (não havia nó a classificar).

### O piso é política, não invariante

O piso de amostragem é **parâmetro de política**: valor inicial, revisável mediante evidência de
campo, fora do schema público e não configurável nesta versão. Mudá-lo não é breaking change; remover
a política, sim. Vive em módulo próprio (`sampling_policy`), separado do mecanismo de emissão — impact
graph, entry points e dependency confidence farão a mesma pergunta e devem consultar **essa** política
em vez de embutir o próprio piso. Pisos diferentes por consumidor são legítimos (parâmetro `floor`);
pisos *espalhados* não. Hoje o piso governa o aviso de sub-evidência em `coverage_context.warning`;
seu escopo natural são os campos semânticos, não o placement.

**O piso não é limiar de confiança estatística.** É barreira operacional contra conclusões
conhecidamente frágeis — não a afirmação de que a partir dele a conclusão é confiável. O valor inicial
pode ser alto demais para um monorepo enorme e baixo demais para um projeto pequeno e crítico; não
pretende resolver isso. Ler `sampling_ratio ≥ piso` como "confiança mínima arquitetural atingida" é
interpretação errada. O que a política garante é só o piso: abaixo dele, sabemos que não basta.

`sampling_ratio` é **propriedade global da execução do Analyze**, não do Observed Placement. Descreve
a evidência disponível para *qualquer* afirmação daquela execução; o Placement apenas consome, e
depende de **um campo** — não navega pelo bloco de métricas.

### Completude de análise

Expressa-se por **par população/evidência**, nunca por booleano dedicado a uma feature:
`file_count` × `files_sampled` no nó, `files_total` × `files_sampled` no mapa. Um campo por informação
semântica (`entry_points_partial`, `services_partial`, …) multiplicaria a mesma verdade e sairia de
sincronia. `files_sampled == 0` significa que **todo** campo semântico daquele nó está sem evidência;
`files_sampled < file_count`, evidência parcial. O consumidor compara os dois números; o Analyze não
emite a interpretação.

### `CANONICAL_SOURCE_EXTENSIONS`

É a **definição oficial de "arquivo de código-fonte"** no Analyze. Nenhum estágio mantém lista própria
ou subconjunto local para responder "isto é fonte?". Subconjuntos por **capacidade** (extrair imports,
por exemplo) são legítimos, mas derivam do conjunto canônico e são nomeados pela capacidade
(`IMPORT_PARSEABLE_EXTENSIONS`).

**O que ele não é:** não representa "todo código existente no projeto" e não é taxonomia universal de
código. É o conjunto de extensões consideradas arquivos-fonte **analisáveis pelo Analyze** — a
definição da população *deste* sistema. Acrescentar SQL, Terraform, YAML, GraphQL ou arquivos de
configuração altera o que o MAES considera população e, por consequência, cobertura, amostragem, funil
e nós emitidos: exige **decisão arquitetural explícita**, nunca um append à constante porque "também é
código".

### `scan_project` — fonte única de verdade para enumeração estrutural

Infraestrutura **compartilhada do pipeline**, não de um estágio. Hoje o Discovery a usa; Dependency
Analysis passa a usá-la quando as arestas migrarem; qualquer etapa futura que precise conhecer a
população usa **exatamente este** inventário. Nenhum estágio cria um segundo scanner.

**Contrato do inventário** — o que um consumidor pode assumir sem verificar: caminhos **relativos
normalizados** em posix; **ordenação determinística**, independente do SO; **sem duplicatas**; **sem o
mesmo arquivo sob dois caminhos** (links simbólicos não são seguidos nem enumerados); **nenhuma
classificação arquitetural**; e **estabilidade temporal** — o contrato é exclusivamente sobre caminho e
existência, então timestamp, permissões, tamanho ou inode **nunca** influenciam a enumeração nem a
ordem.

**O contrato é lógico, não uma representação de memória.** `scan_project` define *quais garantias* o
inventário oferece, não a obrigação de materializar tudo em tuplas. A materialização atual é escolha
de implementação, não invariante arquitetural; uma evolução futura para representação lazy/streaming é
compatível com este contrato e não requer nova ADR.

**Inventário ⟂ interpretação.** Nenhuma classificação semântica, heurística de arquitetura ou política
de coleta é adicionada ao `scan_project`; quem interpreta o inventário são os consumidores.

**Subconjunto de contrato ≠ subconjunto semântico.** O inventário pode conter subconjuntos que derivam
de **definição da plataforma**; nunca subconjuntos que derivam de **interpretação**:

| Subconjunto | Permitido | Motivo |
| --- | --- | --- |
| `source_paths` | **sim** | deriva de contrato da plataforma (`CANONICAL_SOURCE_EXTENSIONS`) |
| `frontend_paths` | não | deriva de interpretação arquitetural |
| `entity_paths` | não | deriva de heurística |
| `controller_paths` | não | deriva de significado |

Teste para decidir um caso novo: *a pertinência ao subconjunto é decidível pela definição canônica, sem
opinar sobre arquitetura?* Se sim, é contrato e pode viver no inventário. Se exige julgamento — mesmo
um julgamento simples e quase sempre certo — é interpretação, e pertence ao consumidor.

**Dados derivados nunca retroalimentam o inventário.** Nenhuma inferência produzida pelo Analyze —
domínio, tipo de nó, camada, aresta, confiança — pode alterar a definição da população. O fluxo é
estritamente população → interpretação, jamais o inverso; um inventário que dependesse do resultado da
própria análise seria circular, o mesmo defeito da cobertura auto-referente.

Consequência para revisão de PR: alterar `scan_project` altera **toda** a cadeia — Discovery, candidate
builder, cobertura, amostragem, métricas e placement. Não é código interno de um estágio; é a base
sobre a qual os outros afirmam fatos.

### Limites de proteção são observáveis

Um limite operacional **não pode parecer ausência de evidência**. Quando a coleta é truncada por
limite (por exemplo, número de raízes de subprojeto analisadas), os contadores são emitidos
(`project_roots_discovered` / `analyzed` / `truncated`), pelo mesmo princípio de `sampling_ratio` +
`insufficient_sample`: a limitação vira dado, não silêncio.

**Regra de leitura:** `is_frontend_project: false` **combinado com** `project_roots_truncated: true`
**não é evidência negativa**. Significa "não encontrei manifesto de frontend entre as raízes que
analisei", não "este projeto não tem frontend". Todo consumidor de um `false` deve considerar
`project_roots_truncated` antes de concluir. Ordenação por prioridade de manifesto reduz a chance de
errar; não a torna nula.

### Structural Transformation Funnel

Nome do conceito: **a sequência de contagens que descreve como a população de arquivos se transforma em
nós do mapa, uma contagem por etapa de redução** —
`source_files → candidate_count → collapsed_count → node_count`.

Descritivo, nunca avaliativo: sem score, sem limiar, sem aderência. Os nomes são parte do conceito —
`source_files` é a **população enumerada**, não "arquivos que o collector achou"; confundir as duas
coisas é a origem do bug do denominador.

**Uma etapa = exatamente uma transformação estrutural, e uma métrica por transformação.** Não podem
coexistir duas contagens da mesma etapa; é a regra que impede o funil de degenerar em
`candidate_total` + `candidate_count` + `raw_candidates` medindo a mesma coisa com números que divergem
no primeiro refactor. Acrescentar etapa é acrescentar campo; nunca sinônimo de etapa existente.

**`candidate_count` é a principal métrica sentinela de regressão estrutural** — política de revisão,
não lei física. Depende **apenas** do inventário e das regras de agrupamento estrutural: não depende da
amostragem de conteúdo, do orçamento, do enrichment semântico nem de nada que varie entre execuções.

> Alterações no seu valor exigem **justificativa explícita no PR** quando não decorrem de mudança
> esperada nas regras estruturais ou no projeto analisado.

Mudanças legítimas existem e não são regressão — acrescentar extensão a `CANONICAL_SOURCE_EXTENSIONS`,
alterar deliberadamente uma regra de agrupamento ou de collapse, introduzir novo tipo estrutural. Nesses
casos a variação é o resultado esperado e o que se pede é que seja **declarada**, não evitada. O que a
regra proíbe é a variação *não explicada*. Sustentada por teste golden, não pela memória de quem revisa.

## Alternativas consideradas

- **Aumentar `_MAX_TOTAL_CHARS`** — rejeitada: trata o sintoma, e o teto volta a saturar conforme o
  projeto cresce. O orçamento existe para caber em janela de LLM, e `build-arch-map` é zero-LLM.
- **Emitir a conclusão de placement com um `⚠️`** — rejeitada: o consumidor já recebeu o path; o aviso
  não desfaz a orientação errada.
- **Um campo booleano de completude por informação semântica** — rejeitada: multiplicaria a mesma
  verdade a cada campo semântico futuro.

## Consequências

- O artefato passa a distinguir o que foi **enumerado** do que foi **lido**, e a insuficiência de
  evidência fica visível em vez de preenchida.
- Repositórios existentes: após `maes upgrade`, a seção de Code Placement fica **omitida** (fail-closed
  sobre artefato de schema anterior) até que `maes build-arch-map` regenere o mapa em 2.1 — omissão é o
  estado seguro. Compatibilidade é responsabilidade do fluxo oficial de upgrade, nunca de procedimento
  manual em release note.
- Toda alteração que modifique contrato público do Analyze deve, **durante o planejamento**, avaliar se
  exige extensão do fluxo de `maes upgrade`, e registrar a conclusão — inclusive quando for "não
  exige". Ver [migrations.md](../development/migrations.md).

## Invariantes preservados

Observed ⟂ Intended ([ADR 0004](0004-observed-vs-intended-placement.md)) · autoridade observacional
([ADR 0005](0005-autoridade-normativa-observacional.md)) · Compiler único · zero-LLM · determinismo
estrutural · sem compliance · sem score de aderência.
