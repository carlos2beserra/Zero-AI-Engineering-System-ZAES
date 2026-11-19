# RFC 0001 — Blueprint como Contrato Inicial de Engenharia

Status: Proposta · Data: 2026-07-13 · Owner: team:architecture

Depende de:
- ADR 0001 — Blueprint como contrato de governança de aplicação homologada
- ADR 0003 — Context Ownership Principle
- ADR 0004 — Observed × Intended Placement + Divergence Visibility
- ADR 0005 — Autoridade Normativa × Observacional
- ADR 0006 — Upgrade de Contrato Blueprint + Proveniência
- ADR 0007 — Enforcement Ownership ("The Compiler is not an architect")

## 1. Resumo executivo

O Blueprint deixa de ser um **catálogo de aplicações homologadas** e passa a ser o
**Contrato Inicial de Engenharia** de um projeto novo. Seu valor **não é geração de
código** — isso permanece com as ferramentas oficiais do ecossistema (Official
First) — e sim a **transferência de conhecimento arquitetural organizacional** para
o projeto, no nascimento, de modo que uma IA sustente os padrões da organização
durante todo o ciclo de vida usando apenas o conhecimento que passou a pertencer ao
projeto.

## 2. Problema

Após a criação, a IA tem stack e bootstrap, mas perde o conhecimento que sustenta o
padrão arquitetural ao longo dos meses: **convenções, boundaries, placement
(intended), nomenclatura, decisões arquiteturais e padrões de teste**. Hoje parte
desse conhecimento só existe no fluxo brownfield (inferido pelo Analyze); no
greenfield ele não é semeado, e a IA não sabe responder "onde crio um módulo
Financeiro?", "onde ficam DTOs/Validators/Repositories?", "quais boundaries nunca
quebrar?".

## 3. Princípios preservados (invariantes)

Context First · Official First · Compiler único · Blueprint ⟂ Analyze · Context
Ownership (ADR 0003) · Observed × Intended (ADR 0004) · Autoridade normativa ×
observacional (ADR 0005) · human ownership do canal normativo · sem compliance no
Analyze · sem Registry/Marketplace/Provider/Planner/Executor/Policy Engine/DSL/
scaffolder.

## 4. Responsabilidades do Blueprint (exatamente quatro)

1. Definir a arquitetura homologada (identidade + stack).
2. Criar o projeto usando **apenas ferramentas oficiais**.
3. Semear o `context/human` inicial (conhecimento arquitetural).
4. Registrar a proveniência **deterministicamente durante o seed** (ver ADR 0006).

Nada além disso.

> **Writer da proveniência (invariante).** O **único** escritor da proveniência
> canônica é o **CLI**, durante `create`/`seed`. Agentes — inclusive o
> `/maes-create` — **nunca** escrevem estado canônico: o agente gera
> intenção/contexto; o CLI grava metadata/proveniência.

## 5. Artefatos do Blueprint

| Artefato | Responsabilidade |
| --- | --- |
| `blueprint.yaml` | Identidade do contrato (`id`/`name`/`type`/`version`/`summary`/`stack`/`seed_human`) |
| `bootstrap.yaml` | Receita Official First (única fonte de execução) |
| `prompt.md` | Comportamento/processo **transitório** do agente de criação (não compilado, não normativo do projeto) |
| `context/human/` | Conhecimento arquitetural **compilável** (normativo, persistido) |

**Autoria do `context/human`** (ADR 0007): a **fonte de verdade é o frontmatter** de
cada documento — `layer`, `type` e `paths`, **todos autoria humana explícita** (o
autor declara, o Compiler executa). **Apenas o formato exato do campo** (nome/
serialização no frontmatter) é [decisão futura]; os conceitos estão fechados. Os
**nomes de arquivo são convenção recomendada**, não normativa (o Compiler honra a
`layer`, não o nome). Arquivos recomendados e suas layers: `compliance`(1), `security`(2),
`contracts`(3), `decisions`(4), `boundaries`(4–5), `domain`(5),
`principles`/`conventions`(6). CONSTRAINT com `paths` → guard de enforcement (tier
pela layer); PATTERN/RATIONALE → contexto sem enforcement.

## 6. Modelo de Seed

O **Blueprint Contract** não é runtime. Ele cria o **Project Seed** — a cópia
inicial materializada em `context/human`. Após o seed, o Project Seed **pertence ao
projeto** (ADR 0003). O Blueprint original não é reconsultado no desenvolvimento
normal.

## 7. Lifecycle do conhecimento

```
Nascimento → Evolução → Observação → Convergência
```

- **Nascimento** — Blueprint → `context/human`.
- **Evolução** — humano → `context/human` (edição direta ou fluxo de sugestão).
- **Observação** — Analyze → `context/inferred`.
- **Convergência** — Compiler (representa ambos os canais; não faz compliance).

Nenhum estágio novo — apenas nomeia o fluxo existente.

## 8. Comportamento quando não existe convenção

Quando **não há Assertion** cobrindo um caso, a IA: (1) não afirma conformidade; (2)
não inventa padrão organizacional; (3) segue o padrão local observado, se houver;
(4) sugere criar convenção via fluxo humano (`/maes-context-add`).

Este comportamento anti-invenção existe em **dois mecanismos complementares**:

1. **`prompt.md`** — instrução operacional **transitória** durante a criação;
2. **contexto compilado** — comportamento **persistente** entregue aos agentes.

**Nenhum dos dois substitui `context/human` como autoridade arquitetural.** São
mecanismos de *comportamento* (como a IA age), não fontes normativas (o que é o
padrão) — logo não competem com o canal normativo.

Informação não compilável (texto vago, sem `layer`/`paths`/tipo declarados)
permanece **contexto** (no máximo PATTERN/RATIONALE), **nunca vira guard**, e o
Compiler **não inventa** significado arquitetural (ADR 0007). O `maes blueprint
validate` **pode** emitir *warning* de higiene — opcional, validação e não
inferência de política.

## 9. Critérios de aceite

- **Guard de placement (intended):** Blueprint enriquecido → `maes sync` → uma regra
  path-bearing aparece em `.maes/synthesis/guards.json` com o tier correto pela
  layer e na seção de guards do `CLAUDE.md`.
- **Não-fusão observed × intended:** com código real, `placement-map.json` reflete
  só o observado; o intended vive em guards/contexto; ambos coexistem e a divergência
  fica visível — nenhum sobrescreve o outro; nenhum `divergence.json`/score.
- **Proveniência:** após create, `config.yaml.blueprint` presente e distinto de
  `meta.maes_version`.
- **Comportamento sem convenção:** caso não coberto (ex.: *event handler*) → a IA
  não afirma conformidade, não inventa regra, segue padrão local e sugere convenção.
- **Teste "meses depois" (Context Ownership):** **remover o acesso ao Blueprint
  original** → sessão limpa → "crie um módulo Financeiro" → a IA deriva
  placement/nomenclatura/boundaries **do `context/human` compilado**, sem varrer o
  projeto inteiro e **sem consultar o Blueprint**.

## 10. Fora de escopo / decisões futuras

Superfície exata de declaração de `type`/`paths` (frontmatter) · algoritmo e inputs
finais do `source_hash` · mecânica do upgrade de contrato (P2) · *intended placement
view* (**removida do escopo**) · incorporar Blueprint ao modelo de camadas em
`overview.mdx` (P2) · validação de coerência `stack × bootstrap × assertions` (P2).
Marcadas **[decisão futura]** — não inventar durante a implementação.
