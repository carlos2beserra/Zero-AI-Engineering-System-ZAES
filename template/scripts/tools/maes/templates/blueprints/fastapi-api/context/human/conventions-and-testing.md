---
layer: 6
ttl: 365d
owner: team:engineering
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Convenções de Código e Testes — FastAPI API Corporativa

> Nomenclatura e padrões de teste definidos pela organização. Padrão de referência
> ajustável por decisão explícita.

## Nomenclatura

- Arquivos e funções em `snake_case`; classes em `PascalCase` — o papel do arquivo nunca fica implícito.
- DTOs de recurso nomeados `<Resource>Create`, `<Resource>Update`, `<Resource>Response` — nunca um DTO genérico sem o papel no nome.
- Services nomeados `<domain>_service.py` com funções-verbo (`create_x`, `list_x`) e a `Session` como argumento keyword-only — nunca posicional.
- Enums de string usam `class X(str, Enum)` com valores lowercase e leitura via `.value` — nunca comparar por nome de membro.

## Testes

- Testes de integração ficam em `tests/test_<feature>.py`, dirigindo as rotas reais via `TestClient` (httpx) — nunca testar detalhes de implementação em vez do comportamento HTTP.
- O schema de teste é criado a partir dos models (SQLite in-memory + `SQLModel.metadata.create_all`), importando `app/db/base` primeiro; a dependency `get_session` é sobreposta para a sessão de teste — os testes nunca dependem do banco de produção nem de migrations para montar o schema.
- Fixtures semeiam a autenticação (usuário + tenant + papel + permissões) e retornam o header `Authorization` + `X-Tenant-ID` — cada teste nunca reimplementa o fluxo de login.
