---
layer: 4
ttl: 180d
owner: team:architecture
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Camada de API e Erros — FastAPI API Corporativa

> Convenções da borda HTTP e do contrato de erro. Padrão de referência definido
> pela organização.

## Routers

- Um router por recurso em `app/api/v1/routes/` (`APIRouter(prefix=..., tags=[...])`), agregados em `app/api/v1/router.py` e montados uma vez em `app/main.py` sob o prefixo de versão — o prefixo `v1` vem de um único valor de settings, nunca repetido à mão.
- Injeção de dependência sempre via `Depends` + `Annotated` (ex.: `SessionDep`, tenant e permissão na assinatura do endpoint) — nunca resolver sessão/auth dentro do corpo do endpoint.
- Paginação usa o utilitário compartilhado (`PaginationParams` / `PaginatedResponse[T]`) em `app/api/v1/schemas/` — cada endpoint de lista nunca reimplementa paginação.

## Contrato de erro

- Erros de aplicação são `AppException` com um `ErrorCode` tipado, tratados por handlers globais registrados em `app/main.py` — o corpo de erro tem sempre o formato `{code, detail}`.
- Endpoints e services nunca retornam formato de erro ad hoc — o handler global é a única fonte do shape de erro.
