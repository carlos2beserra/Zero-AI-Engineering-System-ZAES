# ADR 0007 — Enforcement Ownership (L1/L2): "The Compiler is not an architect"

Status: Aceito · Data: 2026-07-13 · Owner: team:architecture

> **Definição.** O **autor humano** declara a classificação da convenção — `layer`,
> `type`, `paths` e a intenção de enforcement. O **Compiler apenas executa** essa
> declaração. O Compiler não interpreta intenção nem decide política.

## Contexto

Hoje o Compiler infere o `type` de uma convenção por heurística de palavra-chave
(`_classify_type`) e extrai `paths` do texto. Para conteúdo autorado no Blueprint
(o *Contrato Inicial de Engenharia*), isso torna o enforcement **não-determinístico
entre Blueprints**: uma regra frasear fora do padrão vira silenciosamente um
`PATTERN` sem guard, e a organização acredita ter declarado enforcement que não
existe. Efetivamente, o Compiler estaria decidindo política — assumindo papel de
arquiteto.

## Decisão

- **O autor declara** `layer` + `type` (CONSTRAINT / PATTERN / RATIONALE) + `paths`
  + a intenção de enforcement. **O Compiler executa.**
- O Compiler **faz**: parsing, compilação, geração de guards, geração de contexto.
- O Compiler **não faz**: interpretar intenção, decidir *severity*, classificar
  política, inventar enforcement.
- Para conteúdo autorado no Blueprint, **elimina-se** a dependência de detecção por
  palavra-chave, heurística textual e inferência de intenção.
- A **superfície de declaração** (por exemplo, campos de frontmatter para
  `type`/`paths`, complementando o `layer` já honrado) é **[decisão futura]** — o
  *quê* (o autor declara) está fechado; o *como* é detalhe da implementação. **Não
  criar DSL.**

## Alternativas consideradas

- **Manter a inferência por palavra-chave** — rejeitada: enforcement
  não-determinístico; o Compiler viraria arquiteto.

## Consequências

- Enforcement determinístico e previsível entre Blueprints; autoria explícita.
- A implementação precisará de uma superfície de declaração (frontmatter) — sem
  novo formato/DSL, reusando o frontmatter existente.

## Invariantes preservados

Compiler único · sem DSL · Context First.
