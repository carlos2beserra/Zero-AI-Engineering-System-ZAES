---
layer: 2
ttl: 180d
owner: team:security
scope: []
confidence: explicit
source: "blueprint:fastapi-api"
---

# Autenticação e Autorização — FastAPI API Corporativa

> Fronteira de auth definida pela organização. Regras de segurança — tier de
> maior prioridade.

## Autenticação

- Autenticação é por JWT (python-jose, HS256) com o encode/decode isolado no service de token — nunca decodificar token espalhado pelo código.
- Senhas são hasheadas com bcrypt via passlib — nunca armazenar senha em texto puro nem usar hash caseiro.
- A identidade do request vem de uma dependency Bearer (`get_current_user`) — endpoints nunca leem o header de autorização à mão.

## Autorização (RBAC + multi-tenant)

- Autorização é RBAC (Role / Permission / Membership) verificada por dependency-guards (`require_permission` / `require_role`) declaradas na assinatura do endpoint — a checagem de permissão nunca é duplicada dentro do componente.
- O isolamento multi-tenant vem do header `X-Tenant-ID` resolvido por dependency — nunca confiar em tenant vindo do corpo da requisição.
- Segredos (ex.: chaves de provedores) são cifrados em repouso — nunca persistir segredo em texto puro.
