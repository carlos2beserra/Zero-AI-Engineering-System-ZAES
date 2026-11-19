---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:nestjs-api"
---

# Princípios de Engenharia — NestJS API Corporativa

> Padrões homologados para APIs NestJS da organização. Aderentes por padrão em
> todo projeto criado a partir deste Blueprint.

## Padrões do Time

- Sem business logic em controllers — controllers apenas orquestram; regra de negócio vive em domain services.
- Injeção de dependência sempre via construtor — nunca via property ou service locator.
- Validação de entrada com Zod na borda (DTOs/pipes) — não confiar em payload não validado dentro do domínio.
- Erros de domínio sempre tipados (classes de exceção próprias) — sem throw de string ou Error genérico.
- Toda operação que afeta mais de uma tabela roda em transação Prisma explícita.

## Testes

- Testes de integração rodam contra PostgreSQL real (container) — sem mock de repositório Prisma.
- Jest é o runner homologado — não introduzir Vitest/Mocha nesta stack.

## Configuração

- Configuração vem de variáveis de ambiente validadas na inicialização — falhar cedo se faltar env obrigatória.
- Segredos nunca no código nem no git — apenas via env/secret manager.
