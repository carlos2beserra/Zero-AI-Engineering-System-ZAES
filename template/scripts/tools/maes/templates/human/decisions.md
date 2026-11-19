---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: ""
---

# Decisões Arquiteturais (ADRs)

> Decisões técnicas relevantes com seus motivos.
> Inclua APENAS decisões que a IA provavelmente reverteria sem este contexto.
> Formato: a decisão tomada + por que alternativas foram rejeitadas.

## Decisões de Stack

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- ORM escolhido: Prisma (TypeScript) — não migrar para Drizzle sem ADR aprovado; decisão de maio 2024
- Sem GraphQL — REST puro. Tentativa de GraphQL em 2023 falhou por complexidade de N+1
- Message broker: RabbitMQ (não Kafka) — volume atual não justifica Kafka; revisar em Q1 2026
-->

## Decisões de Arquitetura

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Serviço de pagamentos é isolado — nenhum outro serviço chama payments-service diretamente; passa pelo gateway
- Sem foreign keys no banco de produção — integridade garantida na camada de aplicação por decisão de performance
- Módulo de legado: legacy-compat/ existe para clientes enterprise em migração; contrato ativo até Q3 2026 — não remover
-->

## Decisões de Processo

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Migrations usam estratégia expand-contract — nunca breaking changes em uma única migration
- Feature flags via LaunchDarkly — não implementar flags ad-hoc no código
- Sem mocking de banco nos testes de integração — aprendemos com incidente de Q2 2024
-->

## Workarounds Críticos

<!--
Exemplos (não compilados — substitua pelas regras do seu projeto):
- Integração SOAP com parceiro X usa cliente customizado em legacy/soap-client.ts — não substituir por biblioteca genérica; parceiro só aceita SOAP 1.1
- Rate limit do parceiro Y: máximo 10 req/s — throttle implementado em services/external/y-client.ts
-->
