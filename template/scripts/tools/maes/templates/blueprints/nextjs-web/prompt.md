# Next.js Web App Corporativa

Criar uma aplicação web Next.js (App Router) seguindo os padrões definidos pela
engenharia da organização.

Este documento é **contexto operacional** para o agente `/maes-create`. Ele
descreve objetivo, padrões e restrições. **Não executa comandos** — a sequência de
criação vive exclusivamente em `bootstrap/bootstrap.yaml`.

## Objetivo

Uma aplicação Next.js App Router pronta para produção corporativa: tipada,
organizada por features, com estado de servidor via TanStack Query e estado de
cliente/realtime em store dedicado — já com o contexto MAES compilado para IA.

## Stack definida pela organização

- Next.js (App Router) · React · TypeScript · TanStack Query · Zustand ·
  React Hook Form · Zod · shadcn/ui (Radix) · Tailwind · next-intl · pnpm

## Restrições

- **Official First.** Utilizar somente ferramentas oficiais do ecossistema
  (`create-next-app`, `shadcn`, `pnpm`). O MAES nunca reimplementa scaffolding.
- **Não criar arquivos da aplicação manualmente** fora dos passos declarados no
  `bootstrap.yaml`.
- **Não substituir a stack definida** (ex.: não trocar TanStack Query por SWR,
  Zustand por Redux, Zod por Yup, shadcn por outra lib de componentes).
- **Seguir as convenções semeadas em `context/human`** (arquitetura por features,
  boundaries, placement, nomenclatura) ao evoluir o projeto.

## Sequência (declarada no bootstrap.yaml)

1. Scaffold via `create-next-app` (oficial).
2. Instalar a stack definida pela organização.
3. Inicializar shadcn/ui (CLI oficial).
4. Semear contexto organizacional (`maes blueprint seed nextjs-web`).
5. Compilar contexto (`maes sync`).
