---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:react-spa"
---

# Boundaries e Placement — React SPA Corporativo

> Convenções de **onde o código deve nascer** (Intended Placement) e de
> **fronteiras entre features**, homologadas para SPAs React. Padrão de referência
> da organização — ajustável por decisão arquitetural explícita, nunca pela IA.
> Regras com caminho viram guards de enforcement.

## Organização por feature

- Cada feature vive em `src/features/<feature>/` — nunca espalhar código de uma feature fora dela.
- Hooks de dados (TanStack Query) ficam em `src/features/<feature>/hooks/` — nunca chamar `fetch`/axios direto no componente.
- Schemas Zod ficam em `src/features/<feature>/schemas/` — a validação nunca vive inline no componente.
- Rotas são declaradas centralmente em `src/app/routes.tsx` — uma feature nunca registra rota dentro de um componente próprio.

## Componentes e fronteiras

- Componentes base de UI (shadcn/ui) ficam em `src/components/ui/` — nunca duplicar componente base dentro de uma feature.
- Uma feature nunca importa artefatos internos de outra `src/features/**` — o compartilhamento passa por `src/components/**` ou `src/lib/**`.
- Estado de servidor nunca é guardado em estado global manual em `src/features/**` — sempre via TanStack Query.
