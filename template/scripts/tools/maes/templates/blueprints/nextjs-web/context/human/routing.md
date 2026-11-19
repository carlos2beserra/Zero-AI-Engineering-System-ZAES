---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Roteamento — Next.js Web App Corporativa

> Como as rotas são organizadas no App Router. Padrão de referência definido pela
> organização.

## App Router

- Rotas usam o App Router com route-groups por contexto (ex.: `(app)` autenticado e `(auth)` público) — cada grupo tem seu próprio `layout.tsx`.
- O layout do grupo é compartilhado/agnóstico e recebe partes específicas por composição (slots) — nunca embutir lógica de feature no layout.

## Páginas finas

- `page.tsx` é fino: resolve params, aplica o guard de rota e delega a um componente de página da feature — nunca contém lógica de negócio nem chamadas à API.
- A UI e a orquestração vivem no componente de página da feature (`src/features/<feature>/`), não em `src/app/**`.

## Proteção de rota

- A proteção de rota fica na camada de borda apropriada do framework — nunca espalhar redirect de autenticação pelos componentes.
