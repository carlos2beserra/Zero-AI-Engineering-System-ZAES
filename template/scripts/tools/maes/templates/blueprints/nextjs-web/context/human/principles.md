---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:nextjs-web"
---

# Princípios de Engenharia — Next.js Web App Corporativa

> Padrões de engenharia definidos pela organização para aplicações Next.js.
> Padrão de referência aderente por padrão em projetos criados a partir deste
> Blueprint — ajustável por decisão explícita, nunca pela IA.

## Padrões do Time

- Componentes são renderizadores puros — a orquestração (dados, mutações, regras) vive em hooks de feature, nunca no componente.
- Toda a lógica de dados de uma feature fica nos hooks da feature — nunca em `page.tsx` nem em componentes de UI.
- Estado de servidor sempre via TanStack Query; estado de cliente/sessão/realtime em store dedicado — nunca misturar os dois.
- Official First — a estrutura do projeto vem das ferramentas oficiais (`create-next-app`, `shadcn`); o time nunca reimplementa scaffolding.
- Toda string visível ao usuário passa por i18n — nunca literais de UI hardcoded no componente.
