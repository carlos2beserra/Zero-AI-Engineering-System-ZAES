---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Dados e Persistência — FastAPI API Corporativa

> Como os dados são modelados e persistidos. Padrão de referência definido pela
> organização.

## Models e mixins

- Cada agregado é um model SQLModel `table=True` em `app/db/models/` com `__tablename__` explícito — nunca inferir o nome da tabela implicitamente.
- Chave primária é UUID e timestamps são UTC via mixins compartilhados (ex.: `UUIDPrimaryKeyModel`) em `app/db/models/base.py` — nunca redefinir PK/created_at por model.
- Relacionamentos usam `from __future__ import annotations` + `TYPE_CHECKING`; o registro central em `app/db/base.py` importa todos os models e chama `model_rebuild()` — qualquer consumidor que precise das tabelas registradas importa `app/db/base` primeiro.

## Sessão

- A sessão do request vem do generator `get_session` (um único `engine` em `app/db/session.py`) — os services recebem a `Session` injetada, nunca criam engine próprio.

## Migrations (Alembic)

- Migrations ficam em `alembic/versions/` e o `alembic/env.py` obtém a URL de `settings` (fonte única) com `target_metadata = SQLModel.metadata` — nunca hardcodar a URL do banco na migration.
- Seeding de dados de base (ex.: papéis/permissões RBAC) é feito por migration versionada — nunca semear dados fora de migration.

## Fronteira DTO ↔ model

- A conversão entre model de banco e DTO de resposta usa `model_validate` com `from_attributes` — o model SQLModel nunca é serializado direto na resposta.
