---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:react-spa"
---

# Princípios de Engenharia — React SPA Corporativo

> Padrões homologados para SPAs React da organização. Aderentes por padrão em
> todo projeto criado a partir deste Blueprint.

## Padrões do Time

- Estado de servidor sempre via TanStack Query — não guardar dados remotos em estado global manual (Redux/Context).
- Componentes de UI vêm de shadcn/ui — não criar design system paralelo nem trazer outra lib de componentes.
- Estilo via Tailwind — sem CSS-in-JS (styled-components/emotion) nesta stack.
- Validação de formulários e payloads com Zod — schema é a fonte da verdade dos tipos.
- Roteamento com React Router — rotas declaradas de forma centralizada.

## Testes

- Vitest é o runner homologado — não introduzir Jest nesta stack.
- Testar comportamento via Testing Library — sem testar detalhes de implementação.

## Configuração

- Configuração de ambiente via variáveis `VITE_*` — nunca embutir segredos no bundle.
- Build e preview via Vite — não adicionar bundler alternativo.
