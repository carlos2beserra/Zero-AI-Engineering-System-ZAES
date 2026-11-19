---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:react-spa"
---

# Dados e Estado — React SPA Corporativo

> Como dados entram na aplicação e como o estado é dividido. Padrão de referência
> da organização — ajustável por decisão explícita, nunca pela IA. Regras com
> caminho viram guards de enforcement.

## Abstração HTTP única

- Todo acesso HTTP passa por uma única abstração compartilhada em `src/lib/` — as features consomem essa abstração, nunca `fetch`/axios direto em `src/features/**`.
- A abstração HTTP concentra headers, base URL (`VITE_*`) e normalização de erro — features nunca reimplementam esse tratamento.

## Borda de API (mapping)

- As chamadas à API de uma feature ficam em `src/features/<feature>/api/` — retornam tipos de domínio, nunca o payload cru.
- O mapeamento entre o formato da API e o domínio fica em `src/features/<feature>/adapters/*.mapper.ts` — os tipos crus da API nunca vazam para hooks ou componentes.

## TanStack Query

- Cada feature expõe uma fábrica de query keys (`<feature>QueryKeys`) com tuplas `as const` — chaves de query nunca são strings ad hoc espalhadas.
- Mutações invalidam por `queryKeys.all` no `onSuccess` — nunca deixar cache stale silencioso.
- Nomenclatura: `useXxx` para queries, `useCreate/Update/DeleteXxx` para mutações.
- Estado de servidor sempre via TanStack Query — nunca duplicar dados remotos em estado global.
