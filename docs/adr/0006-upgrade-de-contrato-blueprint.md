# ADR 0006 — Upgrade de Contrato Blueprint + Proveniência

Status: Aceito · Data: 2026-07-13 · Owner: team:architecture

> **Definição.** Upgrade de Blueprint é uma **evolução proposta e revisada por
> humano** do conhecimento inicial do projeto — **nunca** migração automática. É
> um ciclo de vida **independente** do `maes upgrade` (infraestrutura do MAES).

## Contexto

Um projeto nasce de um `Blueprint vX`. A organização pode publicar `vY`. Precisamos
de um caminho de evolução opcional que **não** viole o Context Ownership Principle
(ADR 0003) nem transforme o Blueprint em dependência de runtime, e que **não**
reutilize o executor de migrations (que aplica mutações determinísticas de schema —
ferramenta errada para diff de conhecimento humano).

## Decisão

- **Dois ciclos independentes.** `maes upgrade` atualiza a infra do `.maes/`
  (referência: `meta.maes_version`). *Blueprint Contract Upgrade* evolui o
  conhecimento inicial (referência: `blueprint.version`).
- **Fluxo do upgrade de contrato:**
  `vX → diff → proposta humana → aprovação → alteração manual do context/human`.
- O upgrade **nunca**: sobrescreve `context/human`, re-scaffolda, altera
  código/arquitetura existente, ou usa o *executor* de migrations (`Migration.run`).
  Reutiliza **apenas** a *convenção* de versão e o *modelo de cadeia*.
- **Proveniência** (escrita deterministicamente pelo CLI no `seed`/create — ver ADR
  0007 quanto a autoria × escrita), em `config.yaml`, distinta de
  `meta.maes_version`:
  ```yaml
  blueprint:
    id:
    version:
    created_at:
    organization:  # [decisão futura] — derivação não congelada
    source_hash:   # opcional — algoritmo [decisão futura]
  ```
  Semântica: `version` resolve **evolução** ("qual evolução do contrato?");
  `source_hash` resolve **integridade** ("o conteúdo do contrato de origem era
  este?"), cobrindo os quatro artefatos do Blueprint. São **obrigatórios** apenas
  `id`, `version` e `created_at`. `source_hash` permanece **opcional**.
  `organization` é um campo **reservado para evolução futura** e **não é
  obrigatório até que uma ADR congele sua regra de derivação** — nenhum documento
  oficial define hoje sua fonte. Algoritmo/serialização de `source_hash`:
  **[decisão futura]**.
  > **Nota normativa.** Introduzir uma regra de derivação para `organization`
  > constitui **mudança arquitetural** e deve ocorrer por meio de uma **ADR
  > específica** — implementações não devem introduzir regra implícita.

## Alternativas consideradas

- **Sincronização automática ao publicar nova versão** — rejeitada (ADR 0003).
- **Reuso do executor de migrations para aplicar o upgrade** — rejeitada: induz
  auto-aplicação e faz o Blueprint mutar estado (viola Compiler único / human
  ownership).

## Consequências

- Upgrades têm mais valor cedo e degradam conforme o projeto diverge da semente —
  não superinvestir em maquinaria de upgrade.
- A mecânica concreta do upgrade fica como escopo futuro (P2).

## Invariantes preservados

Context Ownership (ADR 0003) · human ownership do canal normativo · sem executor
novo · Official First.
