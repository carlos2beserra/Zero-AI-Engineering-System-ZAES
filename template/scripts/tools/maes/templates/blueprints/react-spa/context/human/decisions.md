---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:react-spa"
---

# Decisões Arquiteturais (ADRs) — React SPA Corporativo

> Decisões de stack e arquitetura homologadas para este Blueprint. A IA não deve
> revertê-las sem um ADR aprovado.

## Decisões de Stack

- Bundler/dev server é Vite — não usar Create React App nem migrar para Next.js (é SPA, não SSR).
- Data fetching é TanStack Query — não usar Redux Toolkit Query/SWR nesta stack.
- Component library é shadcn/ui sobre Radix — não adotar MUI/Ant/Chakra.
- Package manager é pnpm — não usar npm/yarn nesta stack.
- Validação é Zod — não usar Yup/class-validator.

## Decisões de Arquitetura

- Aplicação é SPA client-side — sem SSR/SSG neste Blueprint por decisão de padronização.
- Roteamento client-side com React Router — sem file-based routing.
- Aplicação containerizada via Docker (build estático servido por servidor web) — paridade dev/prod.

## Decisões de Processo

- Variáveis expostas ao cliente sempre com prefixo `VITE_` — o resto nunca vai para o bundle.
