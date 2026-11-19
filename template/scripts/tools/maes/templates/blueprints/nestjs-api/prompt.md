# NestJS API Corporativa

Criar uma API backend corporativa seguindo os padrões homologados pela engenharia.

Este documento é **contexto operacional** para o agente `/maes-create`. Ele
descreve objetivo, padrões e restrições. **Não executa comandos** — a sequência
de criação vive exclusivamente em `bootstrap/bootstrap.yaml`.

## Objetivo

Uma API REST NestJS pronta para produção corporativa: tipada, testável,
containerizada e aderente às decisões da organização, já com o contexto MAES
compilado para IA.

## Stack obrigatória

- NestJS · TypeScript · Prisma · PostgreSQL · Zod · Jest · Docker · pnpm

## Restrições

- **Não substituir tecnologias.** A stack acima é homologada; não trocar Prisma
  por TypeORM, pnpm por npm/yarn, Zod por class-validator, etc.
- **Não criar arquitetura alternativa.** Seguir a estrutura padrão do Nest CLI.
- **Official First.** Utilizar somente ferramentas oficiais do ecossistema
  (Nest CLI, Prisma CLI, pnpm). O MAES nunca reimplementa scaffolding.
- **Não criar arquivos da aplicação manualmente** fora dos passos declarados no
  bootstrap.

## Sequência (declarada no bootstrap.yaml)

1. Scaffold via Nest CLI (oficial).
2. Instalar dependências aprovadas.
3. Configuração padrão (Prisma / PostgreSQL).
4. Semear contexto organizacional (`maes blueprint seed nestjs-api`).
5. Compilar contexto (`maes sync`).
