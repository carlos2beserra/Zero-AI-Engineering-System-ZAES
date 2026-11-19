---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Boundaries e Placement — Next.js Web App Corporativa

> Convenções de **onde o código deve nascer** (Intended Placement) e de
> **fronteiras entre features e código compartilhado**. Padrão de referência
> definido pela organização — ajustável por decisão explícita, nunca pela IA.
> Regras com caminho viram guards de enforcement.

## Organização por feature

- Cada feature vive em `src/features/<feature>/` — nunca espalhar código de uma feature fora dela.
- Transporte/chamadas à API ficam em `src/features/<feature>/*.api.ts` (ou `src/features/<feature>/api/`) — retornam tipos de domínio, nunca DTO cru.
- Hooks de dados (TanStack Query) ficam em `src/features/<feature>/*.hooks.ts` (ou `src/features/<feature>/hooks/`) — a orquestração de dados nunca vive no componente.
- Mapeamento de borda (snake↔camel) fica em `src/features/<feature>/adapters/*.mapper.ts` — tipos `Api*` nunca vazam para hooks, store ou componentes.
- Componentes de feature ficam em `src/features/<feature>/components/` — nunca colocar componente de domínio em `src/shared/**`.

## Fronteiras (dependency rules)

- Código agnóstico de domínio e reutilizável vive em `src/shared/**` — nunca colocar conhecimento de uma feature em `src/shared/**`.
- Uma feature nunca importa artefatos internos de outra `src/features/**` — o compartilhamento passa por `src/shared/**`.
- Todo acesso HTTP passa por uma única abstração compartilhada (ex.: `src/shared/lib/`) — nunca chamar `fetch`/axios direto em `src/features/**`.
