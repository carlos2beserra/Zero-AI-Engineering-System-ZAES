---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Dados e Estado — Next.js Web App Corporativa

> Como dados entram na aplicação e como o estado é dividido. Padrão de referência
> definido pela organização.

## Abstração HTTP única

- Todo acesso HTTP passa por uma única abstração compartilhada (ex.: `src/shared/lib/`) — nunca `fetch`/axios direto em `src/features/**`.
- A abstração HTTP concentra: headers de sessão, prefixo de versão da API, tratamento global de 401/403 e normalização de erro — features nunca reimplementam esse tratamento.

## Borda de API (mapping)

- A conversão entre o formato da API e o domínio (snake↔camel) acontece só em `src/features/<feature>/adapters/*.mapper.ts` — os tipos `Api*` nunca vazam para hooks, store ou componentes.
- Os dois formatos (`Api*` e domínio) são co-definidos na camada de tipos de domínio compartilhada em `src/shared/domain/` — features re-exportam de lá.

## TanStack Query

- Cada feature expõe uma fábrica de query keys (`<feature>QueryKeys`) com tuplas `as const` — chaves nunca são strings ad hoc espalhadas.
- Mutações invalidam por `queryKeys.all` no `onSuccess` — nunca deixar cache stale silencioso.
- Nomenclatura: `useXxx` para queries, `useCreate/Update/DeleteXxx` para mutações.

## Divisão de estado

- Estado de servidor (listas, detalhes, sessão) sempre via TanStack Query — nunca duplicar dados remotos no store global.
- Estado de cliente/sessão/realtime vive num store global dedicado (ex.: `src/shared/store/`) — server state nunca é espelhado ali.
