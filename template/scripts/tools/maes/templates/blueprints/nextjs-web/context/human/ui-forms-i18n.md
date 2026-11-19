---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# UI, Formulários e i18n — Next.js Web App Corporativa

> Convenções de componentes, formulários e internacionalização. Padrão de
> referência definido pela organização.

## Componentes

- Componentes base (design system) vêm do shadcn/ui e ficam em `src/shared/components/ui/` — nunca duplicar primitivo base dentro de uma feature.
- Componentes são renderizadores puros — nunca embutir chamada à API, SSE ou regra de negócio no componente (a orquestração vive nos hooks da feature).
- Estados de carregamento, vazio e erro de listas são centralizados no componente de grid/tabela compartilhado — features nunca reimplementam esses estados.

## Formulários

- Formulários usam React Hook Form + Zod; o schema fica colocado ao formulário (`*.schema.ts`) e o tipo é inferido do schema — nunca validar à mão fora do schema.
- As mensagens do Zod são chaves de i18n (traduzidas na renderização) — nunca literais de mensagem no schema.
- Separação container × presenter: um container detém hooks de mutação, permissão e erro de servidor; o formulário interno é puro (recebe `onSubmit` e `isLoading`) — o formulário nunca chama a API diretamente.

## i18n

- Toda string visível ao usuário passa por i18n como chave — nunca literais de UI hardcoded no componente.
- Os arquivos de locale suportados são mantidos juntos e em sincronia.
