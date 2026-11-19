# FastAPI API Corporativa

Criar uma API backend FastAPI seguindo os padrões definidos pela engenharia da
organização.

Este documento é **contexto operacional** para o agente `/maes-create`. Ele
descreve objetivo, padrões e restrições. **Não executa comandos** — a sequência de
criação vive exclusivamente em `bootstrap/bootstrap.yaml`.

## Objetivo

Uma API REST FastAPI pronta para produção corporativa: tipada (Pydantic v2),
organizada em camadas (api → services → db), com autenticação JWT + RBAC,
persistência via SQLModel/Alembic e testes de integração — já com o contexto MAES
compilado para IA.

## Stack definida pela organização

- FastAPI · Python · Uvicorn · SQLModel · Pydantic v2 · pydantic-settings ·
  Alembic · PostgreSQL · JWT (python-jose) · bcrypt (passlib) · pytest · httpx · uv

## Restrições

- **Official First.** Utilizar somente ferramentas oficiais do ecossistema
  (`uv`, `alembic`). Não há scaffolder monolítico de FastAPI — a estrutura nasce de
  `uv init` + `alembic init`. O MAES nunca reimplementa scaffolding.
- **Não criar arquivos da aplicação manualmente** fora dos passos declarados no
  `bootstrap.yaml`.
- **Não substituir a stack definida** (ex.: não trocar SQLModel por SQLAlchemy
  puro, Alembic por outra ferramenta de migration, uv por poetry/pip).
- **Seguir as convenções semeadas em `context/human`** (camadas, boundaries,
  placement, auth, dados, erros) ao evoluir o projeto.

## Sequência (declarada no bootstrap.yaml)

1. Inicializar o projeto via `uv init` (oficial).
2. Instalar a stack definida pela organização (`uv add`).
3. Inicializar migrations via `uv run alembic init alembic` (CLI oficial).
4. Semear contexto organizacional (`maes blueprint seed fastapi-api`).
5. Compilar contexto (`maes sync`).
