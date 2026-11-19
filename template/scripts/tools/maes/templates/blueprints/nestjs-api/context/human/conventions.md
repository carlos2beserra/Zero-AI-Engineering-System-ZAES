---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:nestjs-api"
---

# Convenções de Código — NestJS API Corporativa

> Nomenclatura, organização de arquivos e padrões de teste homologados. Padrão de
> referência da organização — ajustável por decisão explícita, nunca pela IA.

## Nomenclatura de arquivos

- Arquivos usam o sufixo do papel: `*.controller.ts`, `*.service.ts`, `*.repository.ts`, `*.module.ts` — o sufixo nunca é omitido.
- Schemas Zod nomeados `*.schema.ts` dentro de `src/modules/<domain>/dto/` — nunca schema anônimo espalhado no código.
- Uma classe por arquivo; o nome do arquivo em kebab-case casa com a classe (`payment.service.ts` → `PaymentService`).

## Nomenclatura de classes

- Controllers nomeados `<Domain>Controller`, services `<Domain>Service`, repositórios `<Domain>Repository` — o papel nunca fica implícito no nome.

## Testes

- Testes unitários ficam ao lado do alvo como `src/modules/<domain>/*.spec.ts` — nunca em uma pasta `__tests__` separada nesta stack.
- Testes de integração ficam em `src/modules/<domain>/*.integration-spec.ts` e rodam contra PostgreSQL real (container) — nunca mock de repositório Prisma.
