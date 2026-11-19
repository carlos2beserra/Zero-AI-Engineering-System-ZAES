# React SPA Corporativo

Criar uma Single Page Application React corporativa seguindo os padrões
homologados pela engenharia.

Este documento é **contexto operacional** para o agente `/maes-create`. Ele
descreve objetivo, padrões e restrições. **Não executa comandos** — a sequência
de criação vive exclusivamente em `bootstrap/bootstrap.yaml`.

## Objetivo

Uma SPA React pronta para produção corporativa: tipada, com roteamento, data
fetching, validação e testes homologados, containerizada, já com o contexto MAES
compilado para IA.

## Stack obrigatória

- React · TypeScript · Vite · Tailwind · shadcn/ui · React Router · TanStack Query · Zod · Vitest · Docker · pnpm

## Restrições

- **Não substituir tecnologias.** A stack acima é homologada; não trocar Vite por
  CRA/Next, TanStack Query por Redux/SWR, Tailwind por CSS-in-JS, pnpm por
  npm/yarn, Vitest por Jest, etc.
- **Não criar arquitetura alternativa.** Seguir a estrutura padrão do template
  Vite react-ts.
- **Official First.** Utilizar somente ferramentas oficiais do ecossistema (Vite,
  pnpm, Tailwind CLI, shadcn/ui CLI). O MAES nunca reimplementa scaffolding.
- **Não criar arquivos da aplicação manualmente** fora dos passos declarados no
  bootstrap.

## Sequência (declarada no bootstrap.yaml)

1. Scaffold via Vite (oficial, template react-ts).
2. Instalar dependências aprovadas.
3. Configuração padrão (Tailwind + shadcn/ui).
4. Semear contexto organizacional (`maes blueprint seed react-spa`).
5. Compilar contexto (`maes sync`).
