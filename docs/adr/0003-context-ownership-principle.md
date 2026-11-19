# ADR 0003 — Context Ownership Principle

Status: Aceito · Data: 2026-07-13 · Owner: team:architecture

> **Definição.** Depois que um Blueprint cria um projeto, **o projeto é o
> proprietário permanente do seu conhecimento arquitetural**. O Blueprint é a
> **origem inicial** desse conhecimento, **não uma dependência viva** de runtime.

## Contexto

A Fase do Blueprint como *Contrato Inicial de Engenharia* (ver ADR 0001) exige que
o Blueprint semeie conhecimento arquitetural suficiente para uma IA desenvolver o
projeto por meses. Isso poderia sugerir, incorretamente, que o Blueprint
"acompanha" o projeto — consultado em runtime, governando os projetos existentes e
sincronizando convenções automaticamente. Esse acoplamento criaria uma dependência
central, quebraria a autonomia do projeto e abriria caminho para compliance
implícito.

## Decisão

```
Blueprint Contract → seed inicial → context/human do projeto → Compiler
                                    → Assertions / Guards / Context
```

1. O Blueprint **não** é dependência de runtime.
2. O Blueprint original **não** é consultado durante o desenvolvimento normal. As
   únicas exceções são: upgrade explícito de contrato, comparação histórica entre
   versões e auditoria de proveniência.
3. Atualizar o Blueprint da organização **não** altera projetos existentes.
4. A evolução do conhecimento do projeto acontece **apenas por decisão humana
   explícita** (ver ADR 0006).

Pergunta de referência — *"Se a organização atualizar o Blueprint da empresa, meu
projeto muda automaticamente?"* → **Não.** Novos projetos usam o novo contrato;
projetos existentes permanecem com seu conhecimento atual.

## Alternativas consideradas

- **Blueprint como referência viva consultada em runtime** — rejeitada:
  acoplamento, governança central implícita, quebra da autonomia do projeto.
- **Sincronização automática de convenções** — rejeitada: destrói edições locais e
  transforma o Blueprint em mecanismo de compliance.

## Consequências

- Projetos são autônomos; não há dependência do catálogo em runtime.
- O conhecimento envelhece e é mantido pela Governance Layer existente
  (`owner`/`ttl`/staleness); upgrades são opt-in.
- Habilita o **teste "meses depois"**: com o Blueprint inacessível, a IA deve
  derivar placement/nomenclatura/boundaries apenas do `context/human` compilado.

## Invariantes preservados

Context First · Compiler único · Blueprint ⟂ Analyze.
