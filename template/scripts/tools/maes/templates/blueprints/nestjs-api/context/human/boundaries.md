---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nestjs-api"
---

# Boundaries e Placement — NestJS API Corporativa

> Convenções de **onde o código deve nascer** (Intended Placement) e de
> **fronteiras entre módulos**, homologadas para APIs NestJS. São o padrão de
> referência da organização — ajustável por decisão arquitetural explícita, nunca
> pela IA. Regras com caminho viram guards de enforcement.

## Organização de módulos

- Cada domínio vive em `src/modules/<domain>/` — nunca criar código de domínio fora de um módulo.
- Controllers ficam em `src/modules/<domain>/*.controller.ts` — nunca na raiz do projeto.
- Services de domínio ficam em `src/modules/<domain>/*.service.ts` — regra de negócio nunca vive no controller.
- Repositórios (acesso Prisma) ficam em `src/modules/<domain>/*.repository.ts` — controllers nunca acessam Prisma diretamente.
- DTOs de entrada/saída ficam em `src/modules/<domain>/dto/` — nunca expor entidade Prisma direto na borda HTTP.
- Schemas de validação Zod ficam em `src/modules/<domain>/dto/*.schema.ts` — a validação nunca vive dentro do service.

## Regras de dependência (boundaries)

- Um módulo nunca importa artefatos internos de outro `src/modules/**` — a dependência entre domínios passa por serviços exportados no `*.module.ts`.
- Código transversal compartilhado vive em `src/shared/**` — nunca duplicar utilitário entre módulos.
- `src/modules/**` nunca importa de `src/main.ts` nem de código de bootstrap da aplicação.
