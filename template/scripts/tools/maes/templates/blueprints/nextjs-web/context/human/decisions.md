---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Decisões Arquiteturais (ADRs) — Next.js Web App Corporativa

> Decisões de stack e arquitetura definidas pela organização para este Blueprint.
> A IA não deve revertê-las sem um ADR aprovado.

## Decisões de Stack

- Framework é Next.js com App Router — não usar Pages Router nem trocar por outro framework.
- Data fetching de servidor é TanStack Query — não usar SWR/Redux Toolkit Query nesta stack.
- Estado de cliente/realtime é Zustand — não introduzir Redux/MobX nesta stack.
- Validação é Zod (com React Hook Form via `@hookform/resolvers`) — não usar Yup/class-validator.
- Componentes base são shadcn/ui sobre Radix — não adotar MUI/Ant/Chakra.
- Package manager é pnpm — não usar npm/yarn nesta stack.

## Decisões de Arquitetura

- Arquitetura por features (feature-slice) — cada capacidade de negócio é uma feature; não criar camadas service/repository/DI ao estilo backend.
- Acesso a dados passa por uma única abstração HTTP compartilhada — não espalhar clientes HTTP nem chamar `fetch` direto nas features.
- Sessão de autenticação compatível com SSR e segura — token nunca em armazenamento só-cliente que quebre SSR ou segurança.
- Proteção de rota fica na camada de borda apropriada do framework — não espalhar redirect de auth pelos componentes.
