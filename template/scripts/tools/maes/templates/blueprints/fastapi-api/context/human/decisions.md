---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Decisões Arquiteturais (ADRs) — FastAPI API Corporativa

> Decisões de stack e arquitetura definidas pela organização para este Blueprint.
> A IA não deve revertê-las sem um ADR aprovado.

## Decisões de Stack

- Framework é FastAPI com Uvicorn — não trocar por Flask/Django nesta stack.
- ORM/modelagem é SQLModel sobre Pydantic v2 — não usar SQLAlchemy puro nem outra ODM.
- Migrations são geridas por Alembic — não aplicar mudança de schema fora de migration.
- Banco é PostgreSQL (driver psycopg v3) — decisão padrão da organização.
- Package manager e runner é uv — não usar poetry/pip/pipenv nesta stack.

## Decisões de Arquitetura

- Arquitetura em camadas com dependência unidirecional: `api → services → db`; `infrastructure` e `domain` são isolados; `workers` reusam services e nunca importam o `api`.
- Services são módulos de funções por domínio (recebem a `Session` injetada) — não há camada de repository e não se usa service como classe com estado.
- DTOs de API (Pydantic) são separados dos models de banco (SQLModel) — nunca expor o model de tabela direto na borda HTTP.
- Erros de aplicação são exceções tipadas (`AppException` + `ErrorCode`) tratadas por handlers globais — não usar `ValueError`/`LookupError` como contrato de erro.
- Conversão de model para resposta usa `model_validate` com `from_attributes` — não montar a resposta campo-a-campo à mão.
