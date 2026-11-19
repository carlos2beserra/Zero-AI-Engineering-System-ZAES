---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nestjs-api"
---

# Decisões Arquiteturais (ADRs) — NestJS API Corporativa

> Decisões de stack e arquitetura homologadas para este Blueprint. A IA não deve
> revertê-las sem um ADR aprovado.

## Decisões de Stack

- ORM é Prisma — não migrar para TypeORM/Drizzle sem ADR aprovado.
- Banco é PostgreSQL — decisão padrão da organização para APIs NestJS.
- Package manager é pnpm — não usar npm/yarn nesta stack.
- Validação de schema é Zod — não usar class-validator/joi nesta stack.

## Decisões de Arquitetura

- API REST — sem GraphQL neste Blueprint por decisão de padronização.
- Camadas: controller → service (domínio) → repositório (Prisma). Controllers não acessam Prisma diretamente.
- Aplicação containerizada via Docker desde o início — paridade dev/prod.

## Decisões de Processo

- Migrations Prisma versionadas no git — nunca alterar o schema de produção fora de migration.
