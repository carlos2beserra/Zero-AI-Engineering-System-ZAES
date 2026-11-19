# ADR 0005 — Autoridade Normativa × Observacional

Status: Aceito · Data: 2026-07-13 · Owner: team:architecture

> **Definição.** Substitui a formulação "humano vence". O canal humano
> (`context/human`) tem autoridade **normativa** ("como *deve* ser"); o canal
> inferido (Analyze) tem autoridade **observacional** ("como *está*"). Não
> competem — representam fatos de tipos diferentes.

## Contexto

A resolução de conflito entre conhecimento humano e inferido era descrita como
"humano vence sobre inferido". Essa linguagem trata dois fatos de naturezas
diferentes (intenção × observação) como reivindicações competindo pelo mesmo fato,
e empurra o Compiler para o papel de juiz de conformidade.

## Decisão

- Formaliza-se a distinção de **autoridade**: normativa (humano) × observacional
  (inferido).
- O Compiler **representa** ambos os canais. O Compiler **não decide quem está
  correto**, **não resolve** divergências arquiteturais e **não** calcula
  aderência.

Nota de implementação (comportamento atual, não alterado por esta ADR): no dedup
de assertions duplicadas, a de maior autoridade prevalece por `CONFIDENCE_RANK`
preservando a proveniência absorvida em `merge_history`; divergências não
resolvidas são emitidas em `conflicts`. Isso é mecanismo de **representar**
conflito — nunca de julgar conformidade.

## Alternativas consideradas

- **Manter "humano vence"** — rejeitada: trata fatos diferentes como conflito e
  induz o Compiler a compliance.

## Consequências

- A distinção de autoridade é o mecanismo de governança **sem** enforcement
  automático.
- Base conceitual da Divergence Visibility Policy (ADR 0004).

## Invariantes preservados

Compiler único · sem compliance · Observed × Intended (ADR 0004).
