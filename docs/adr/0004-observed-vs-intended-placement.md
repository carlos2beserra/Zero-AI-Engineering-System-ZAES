# ADR 0004 — Observed × Intended Placement + Divergence Visibility

Status: Aceito · Data: 2026-07-13 · Owner: team:architecture

> **Definição.** *Intended Placement* (normativo, canal humano) e *Observed
> Placement* (observacional, Analyze) são conceitos **distintos** que **nunca**
> compartilham artefato. A divergência entre eles é **informação visível**, nunca
> compliance.

## Contexto

O `placement-map.json` nasceu como representação do conhecimento **observado** pelo
Analyze (`architecture_map.json` → `placement-map.json`): responde "onde o código
está hoje?". Houve a tentação de projetar o placement **declarado** pela
organização (humano) dentro do mesmo artefato — fundindo intenção com observação e
introduzindo uma lógica de "humano vence" no mapa observacional.

## Decisão

- **Intended Placement.** Fonte: `context/human` do projeto. Autoridade:
  **normativa**. Pergunta: "onde o código *deveria* nascer?". Fluxo:
  `context/human → Compiler → Assertions → Guards + Context`.
- **Observed Placement.** Fonte: Analyze. Artefato: `placement-map.json`.
  Autoridade: **observacional**. Pergunta: "onde o código *está* hoje?".
- Regras:
  - `placement-map.json` permanece **exclusivo do Analyze**.
  - O Blueprint **nunca** escreve nele; `context/human` **nunca** o alimenta.
  - **Não** existe `intended-placement-map` nem qualquer terceira representação.
- **Divergence Visibility Policy.** A diferença entre intended e observed é uma
  **leitura** feita pelo consumidor (IA ou humano) sobre dois artefatos
  independentes. **Nenhum componente do MAES gera** `divergence.json`, *adherence
  score* ou *compliance report*. Diante de divergência: **manter ambos, tornar
  visível, permitir decisão humana** — nunca corrigir automaticamente, remover a
  regra humana ou marcar violação.

## Alternativas consideradas

- **Fusão no `placement-map.json` com "humano vence"** — rejeitada: confunde fonte
  com projeção, deriva para um segundo placement-map e para compliance.

## Consequências

- Os dois canais coexistem sem sobrescrita; a divergência fica visível sem
  enforcement automático.
- O `placement-map.json` permanece intacto como o mapa observacional do Analyze.

## Invariantes preservados

Blueprint ⟂ Analyze · Compiler único · sem compliance (ver ADR 0005).
